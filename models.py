from datetime import datetime, timedelta
from flask_login import UserMixin
from extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"))
)

likes = db.Table(
    "likes",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.Column("post_id", db.Integer, db.ForeignKey("post.id", ondelete="CASCADE"))
)

story_views = db.Table(
    "story_views",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("story_id", db.Integer, db.ForeignKey("story.id"))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(120), unique=True, nullable=False)
    nickname = db.Column(db.String(120), nullable=True)

    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    image_file = db.Column(db.String(120))
    bio = db.Column(db.String(300))
    is_private = db.Column(db.Boolean, default=False)

    followed = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic"
    )

    follow_requests = db.Table(
        "follow_requests",
        db.Column("sender_id", db.Integer, db.ForeignKey("user.id")),
        db.Column("receiver_id", db.Integer, db.ForeignKey("user.id"))
    )

    requests_sent = db.relationship(
        "User",
        secondary=follow_requests,
        primaryjoin=(follow_requests.c.sender_id == id),
        secondaryjoin=(follow_requests.c.receiver_id == id),
        backref=db.backref("requests_received", lazy="dynamic"),
        lazy="dynamic"
    )

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id
        ).count() > 0

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(120))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    author = db.relationship("User", backref="posts")
    comments = db.relationship("Comment", backref="post", cascade="all, delete")
    likers = db.relationship("User", secondary=likes, backref="liked_posts")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id", ondelete="CASCADE"), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_seen = db.Column(db.Boolean, default=False)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_file = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=24)
    )

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref="stories")

    views = db.relationship(
        "User",
        secondary=story_views,
        backref="viewed_stories"
    )