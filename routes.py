from datetime import datetime
from flask import render_template, redirect, url_for, request
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import app, socketio
from extensions import db
from models import User, Post, Comment, Message, Notification, Story
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
import os
import uuid

@app.route("/")
@login_required
def home():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    stories = Story.query.filter(Story.expires_at > datetime.utcnow()).all()
    return render_template("home.html", posts=posts, stories=stories)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form["username"].strip().lower()
        email = request.form["email"]

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return render_template(
                "register.html",
                error="Username already taken"
            )

        hashed = generate_password_hash(request.form["password"])

        user = User(
            username=username,
            nickname=request.form.get("nickname"),
            email=email,
            password=hashed
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("home"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        image = request.files.get("image")
        filename = None

        if image and image.filename:
            filename = secure_filename(str(uuid.uuid4()) + "_" + image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        post = Post(
            content=request.form["content"],
            image_file=filename,
            author=current_user
        )

        db.session.add(post)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("create_post.html")

@app.route("/post/<int:post_id>/like")
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)

    if current_user in post.likers:
        post.likers.remove(current_user)
        db.session.commit()
    else:
        post.likers.append(current_user)

        if post.author != current_user:
            notification = Notification(
                message=f"{current_user.username} liked your post.",
                user_id=post.author.id
            )
            db.session.add(notification)
            db.session.commit()

            socketio.emit(
                "new_notification",
                {"message": notification.message},
                room=str(post.author.id)
            )
        else:
            db.session.commit()

    return redirect(url_for("home"))

@app.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        return redirect(url_for("home"))

    if post.image_file:
        path = os.path.join(app.config["UPLOAD_FOLDER"], post.image_file)
        if os.path.exists(path):
            os.remove(path)

    db.session.delete(post)
    db.session.commit()
    return redirect(url_for("home"))

@app.route("/post/<int:post_id>/comment", methods=["POST"])
@login_required
def comment_post(post_id):
    post = Post.query.get_or_404(post_id)

    comment = Comment(
        content=request.form["content"],
        author=current_user,
        post_id=post_id
    )

    db.session.add(comment)

    if post.author != current_user:
        notification = Notification(
            message=f"{current_user.username} commented on your post.",
            user=post.author
        )
        db.session.add(notification)

    db.session.commit()
    return redirect(url_for("home"))

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

@app.route("/profile/<username>")
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).all()

    mutual = [
        u for u in user.followers
        if current_user.is_following(u)
    ]

    return render_template(
        "profile.html",
        user=user,
        posts=posts,
        mutual_count=len(mutual)
    )

@app.route("/chat")
@login_required
def chat_list():
    users = User.query.filter(User.id != current_user.id).all()

    chat_data = []

    for user in users:
        last_message = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user.id)) |
            ((Message.sender_id == user.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()

        unread_count = Message.query.filter_by(
            sender_id=user.id,
            receiver_id=current_user.id
        ).count()

        chat_data.append({
            "user": user,
            "last_message": last_message,
            "unread_count": unread_count
        })

    return render_template("chat_list.html", chat_data=chat_data)

@app.route("/chat/<username>", methods=["GET", "POST"])
@login_required
def chat(username):
    user = User.query.filter_by(username=username).first_or_404()

    if request.method == "POST":
        content = request.form.get("message")

        if content:
            msg = Message(
                sender_id=current_user.id,
                receiver_id=user.id,
                content=content
            )
            db.session.add(msg)

            notification = Notification(
                message=f"New message from {current_user.username}.",
                user_id=user.id
            )
            db.session.add(notification)

            db.session.commit()

            socketio.emit(
                "new_notification",
                {"message": notification.message},
                room=str(user.id)
            )

            return redirect(url_for("chat", username=username))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user.id)) |
        ((Message.sender_id == user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    Message.query.filter_by(
        sender_id=user.id,
        receiver_id=current_user.id,
        is_seen=False
    ).update({"is_seen": True})

    db.session.commit()

    return render_template("chat.html", messages=messages, user=user)

@app.route("/follow/<username>")
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first_or_404()

    if user == current_user:
        return redirect(url_for("profile", username=username))

    if user.is_private:
        current_user.requests_sent.append(user)
        db.session.commit()
        return redirect(url_for("profile", username=username))

    current_user.follow(user)

    notification = Notification(
        message=f"{current_user.username} started following you.",
        user_id=user.id
    )
    db.session.add(notification)

    db.session.commit()

    socketio.emit(
        "new_notification",
        {"message": notification.message},
        room=str(user.id)
    )

    return redirect(url_for("profile", username=username))

@app.route("/unfollow/<username>")
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first_or_404()

    if user == current_user:
        return redirect(url_for("profile", username=username))

    current_user.unfollow(user)
    db.session.commit()

    return redirect(url_for("profile", username=username))

@app.route("/search")
@login_required
def search():
    query = request.args.get("q")

    if query:
        users = User.query.filter(User.username.ilike(f"%{query}%")).all()
    else:
        users = []

    return render_template("search.html", users=users, query=query)

@app.route("/followers/<username>")
@login_required
def followers_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers = user.followers.all()
    return render_template("followers.html", user=user, followers=followers)


@app.route("/following/<username>")
@login_required
def following_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    following = user.followed.all()
    return render_template("following.html", user=user, following=following)

@app.route("/notifications")
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).all()
    return render_template("notifications.html", notifications=notifications)

@app.route("/ajax_follow/<username>")
@login_required
def ajax_follow(username):
    user = User.query.filter_by(username=username).first_or_404()

    if current_user.is_following(user):
        current_user.unfollow(user)
        db.session.commit()
        return {"status": "Follow"}
    else:
        current_user.follow(user)
        db.session.commit()
        return {"status": "Unfollow"}

@app.route("/add_story", methods=["GET", "POST"])
@login_required
def add_story():
    if request.method == "POST":
        image = request.files.get("image")

        if image and image.filename:
            filename = secure_filename(str(uuid.uuid4()) + "_" + image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            story = Story(
                image_file=filename,
                user=current_user
            )

            db.session.add(story)
            db.session.commit()

            return redirect(url_for("home"))

    return render_template("add_story.html")

@app.route("/story/<username>")
@login_required
def view_story(username):
    user = User.query.filter_by(username=username).first_or_404()

    if user != current_user and not current_user.is_following(user):
        return redirect(url_for("home"))

    stories = Story.query.filter(
        Story.user == user,
        Story.expires_at > datetime.utcnow()
    ).all()

    for story in stories:
        if current_user not in story.views:
            story.views.append(current_user)

    db.session.commit()

    return render_template("view_story.html", stories=stories, user=user)

@app.route("/delete_story/<int:story_id>", methods=["POST"])
@login_required
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)

    if story.user != current_user:
        return redirect(url_for("home"))

    if story.image_file:
        path = os.path.join(app.config["UPLOAD_FOLDER"], story.image_file)
        if os.path.exists(path):
            os.remove(path)

    db.session.delete(story)
    db.session.commit()

    return redirect(url_for("home"))

from flask import request, redirect, url_for
from flask_login import current_user, login_required

@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.username = request.form.get("username")
        current_user.bio = request.form.get("bio")
        db.session.commit()
        return redirect(url_for("profile", username=current_user.username))

    return render_template("edit_profile.html", user=current_user)