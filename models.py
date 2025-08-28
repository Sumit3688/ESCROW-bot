from app import db
from datetime import datetime, timezone
from sqlalchemy import Enum
import enum

class UserStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"

class TransactionStatus(enum.Enum):
    CREATED = "created"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_RECEIVED = "payment_received"
    IN_ESCROW = "in_escrow"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class DisputeStatus(enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"

class CryptoCurrency(enum.Enum):
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    USDT = "usdt"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    status = db.Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    reputation_score = db.Column(db.Float, default=0.0)
    total_trades = db.Column(db.Integer, default=0)
    successful_trades = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    seller_transactions = db.relationship('Transaction', foreign_keys='Transaction.seller_id', backref='seller', lazy='dynamic')
    buyer_transactions = db.relationship('Transaction', foreign_keys='Transaction.buyer_id', backref='buyer', lazy='dynamic')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_hash = db.Column(db.String(128), unique=True, nullable=False)
    
    # Parties involved
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Transaction details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Numeric(18, 8), nullable=False)
    currency = db.Column(Enum(CryptoCurrency), nullable=False)
    status = db.Column(Enum(TransactionStatus), default=TransactionStatus.CREATED)
    
    # Wallet information
    escrow_wallet_address = db.Column(db.String(128), nullable=False)
    escrow_wallet_private_key = db.Column(db.Text, nullable=False)  # Encrypted
    seller_wallet_address = db.Column(db.String(128), nullable=True)
    
    # Commission and fees
    commission_rate = db.Column(db.Float, default=0.02)  # 2% default
    commission_amount = db.Column(db.Numeric(18, 8), default=0)
    network_fee = db.Column(db.Numeric(18, 8), default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    payment_received_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Transaction details
    blockchain_tx_hash = db.Column(db.String(128), nullable=True)
    confirmation_count = db.Column(db.Integer, default=0)
    
    # Relationships
    disputes = db.relationship('Dispute', backref='transaction', lazy='dynamic')
    notifications = db.relationship('Notification', backref='transaction', lazy='dynamic')

class Dispute(db.Model):
    __tablename__ = 'disputes'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    reason = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(Enum(DisputeStatus), default=DisputeStatus.OPEN)
    
    # Resolution
    resolved_by_admin = db.Column(db.Boolean, default=False)
    resolution_notes = db.Column(db.Text, nullable=True)
    resolution_amount = db.Column(db.Numeric(18, 8), nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    initiator = db.relationship('User', foreign_keys=[initiated_by], backref='initiated_disputes')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='notifications')

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(64), nullable=True)
    is_super_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
