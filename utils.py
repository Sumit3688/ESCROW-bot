import os
import hashlib
import secrets
import logging
from cryptography.fernet import Fernet
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Encryption key for private keys (in production, use proper key management)
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def generate_transaction_hash() -> str:
    """Generate a unique transaction hash"""
    timestamp = str(datetime.now().timestamp())
    random_bytes = secrets.token_hex(16)
    combined = f"{timestamp}-{random_bytes}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16].upper()

def encrypt_private_key(private_key: str) -> str:
    """Encrypt a private key for secure storage"""
    try:
        encrypted_key = fernet.encrypt(private_key.encode())
        return encrypted_key.decode()
    except Exception as e:
        logger.error(f"Error encrypting private key: {e}")
        return ""

def decrypt_private_key(encrypted_key: str) -> str:
    """Decrypt a private key"""
    try:
        decrypted_key = fernet.decrypt(encrypted_key.encode())
        return decrypted_key.decode()
    except Exception as e:
        logger.error(f"Error decrypting private key: {e}")
        return ""

def format_currency(amount: float, currency: str) -> str:
    """Format currency amount with appropriate precision"""
    precision_map = {
        'bitcoin': 8,
        'ethereum': 6,
        'usdt': 2
    }
    
    precision = precision_map.get(currency.lower(), 4)
    
    if currency.lower() == 'bitcoin':
        symbol = '₿'
    elif currency.lower() == 'ethereum':
        symbol = 'Ξ'
    elif currency.lower() == 'usdt':
        symbol = '₮'
    else:
        symbol = currency.upper()
    
    return f"{symbol} {amount:.{precision}f}"

def validate_wallet_address(address: str, currency: str) -> bool:
    """Validate cryptocurrency wallet address format"""
    try:
        if currency.lower() == 'bitcoin':
            # Bitcoin address validation (simplified)
            return (
                (address.startswith('1') and len(address) in [26, 35]) or
                (address.startswith('3') and len(address) in [26, 35]) or
                (address.startswith('bc1') and len(address) in [42, 62])
            )
        elif currency.lower() in ['ethereum', 'usdt']:
            # Ethereum address validation
            return (address.startswith('0x') and 
                   len(address) == 42 and 
                   all(c in '0123456789abcdefABCDEF' for c in address[2:]))
        return False
    except Exception as e:
        logger.error(f"Address validation error: {e}")
        return False

def calculate_transaction_fee(amount: float, currency: str) -> float:
    """Calculate appropriate transaction fee for blockchain operations"""
    # Simplified fee calculation
    fee_rates = {
        'bitcoin': 0.0001,    # 0.0001 BTC
        'ethereum': 0.002,    # 0.002 ETH
        'usdt': 5.0          # 5 USDT (covers ETH gas)
    }
    
    base_fee = fee_rates.get(currency.lower(), 0.001)
    
    # For percentage-based fees
    if currency.lower() in ['ethereum']:
        return max(base_fee, amount * 0.001)  # Minimum fee or 0.1% of amount
    
    return base_fee

def format_timestamp(timestamp: datetime, format_type: str = 'full') -> str:
    """Format timestamp for display"""
    if not timestamp:
        return "N/A"
    
    formats = {
        'full': '%Y-%m-%d %H:%M:%S UTC',
        'date': '%Y-%m-%d',
        'time': '%H:%M:%S',
        'relative': None  # Would implement relative time formatting
    }
    
    if format_type == 'relative':
        # Simple relative time implementation
        now = datetime.now(timestamp.tzinfo)
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"
    
    return timestamp.strftime(formats.get(format_type, formats['full']))

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input"""
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    sanitized = text.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized

def is_admin_user(telegram_id: int) -> bool:
    """Check if user is an administrator"""
    admin_ids = os.environ.get("ADMIN_TELEGRAM_IDS", "").split(',')
    return str(telegram_id) in admin_ids

def generate_invoice_number() -> str:
    """Generate unique invoice number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    random_part = secrets.token_hex(4).upper()
    return f"INV-{timestamp}-{random_part}"

def calculate_success_rate(successful: int, total: int) -> float:
    """Calculate success rate percentage"""
    if total == 0:
        return 0.0
    return (successful / total) * 100

def truncate_address(address: str, start_chars: int = 6, end_chars: int = 4) -> str:
    """Truncate long addresses for display"""
    if not address or len(address) <= start_chars + end_chars:
        return address
    
    return f"{address[:start_chars]}...{address[-end_chars:]}"

def validate_amount(amount_str: str, min_amount: float = 0.0001, max_amount: float = 1000000) -> tuple[bool, Optional[float], str]:
    """Validate transaction amount"""
    try:
        amount = float(amount_str)
        
        if amount <= 0:
            return False, None, "Amount must be greater than zero"
        
        if amount < min_amount:
            return False, None, f"Minimum amount is {min_amount}"
        
        if amount > max_amount:
            return False, None, f"Maximum amount is {max_amount}"
        
        return True, amount, "Valid amount"
        
    except ValueError:
        return False, None, "Invalid amount format"

def get_network_confirmations_required(currency: str) -> int:
    """Get required confirmations for different networks"""
    confirmations = {
        'bitcoin': 1,
        'ethereum': 3,
        'usdt': 3
    }
    return confirmations.get(currency.lower(), 3)

def log_transaction_event(transaction_id: int, event: str, details: str = ""):
    """Log important transaction events"""
    logger.info(f"Transaction {transaction_id}: {event} - {details}")

class TransactionValidator:
    """Utility class for transaction validation"""
    
    @staticmethod
    def validate_trade_creation(title: str, description: str, amount: float, currency: str) -> tuple[bool, str]:
        """Validate trade creation parameters"""
        if not title or len(title.strip()) < 3:
            return False, "Title must be at least 3 characters long"
        
        if len(title) > 200:
            return False, "Title cannot exceed 200 characters"
        
        if not description or len(description.strip()) < 10:
            return False, "Description must be at least 10 characters long"
        
        if len(description) > 2000:
            return False, "Description cannot exceed 2000 characters"
        
        valid_amount, validated_amount, amount_error = validate_amount(str(amount))
        if not valid_amount:
            return False, amount_error
        
        if currency.lower() not in ['bitcoin', 'ethereum', 'usdt']:
            return False, "Unsupported currency"
        
        return True, "Valid trade parameters"
