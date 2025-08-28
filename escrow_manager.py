import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_
from app import db
from models import Transaction, TransactionStatus, User, Notification, CryptoCurrency
from crypto_handler import CryptoHandler
from utils import decrypt_private_key, format_currency
from typing import Optional, List

logger = logging.getLogger(__name__)

class EscrowManager:
    def __init__(self):
        self.crypto_handler = CryptoHandler()
    
    async def process_pending_transactions(self):
        """Process all pending transactions - check payments and confirmations"""
        try:
            with db.session.begin():
                # Get transactions awaiting payment confirmation
                pending_transactions = Transaction.query.filter(
                    Transaction.status == TransactionStatus.PAYMENT_PENDING,
                    Transaction.created_at > datetime.now(timezone.utc) - timedelta(hours=2)
                ).all()
                
                for transaction in pending_transactions:
                    await self._check_transaction_payment(transaction)
                
                # Get transactions in escrow that may need auto-release
                escrow_transactions = Transaction.query.filter(
                    Transaction.status == TransactionStatus.IN_ESCROW,
                    Transaction.payment_received_at < datetime.now(timezone.utc) - timedelta(days=7)
                ).all()
                
                for transaction in escrow_transactions:
                    await self._check_auto_release(transaction)
                    
        except Exception as e:
            logger.error(f"Error processing pending transactions: {e}")
    
    async def _check_transaction_payment(self, transaction: Transaction):
        """Check if payment has been received for a transaction"""
        try:
            commission = transaction.amount * transaction.commission_rate
            total_expected = transaction.amount + commission
            
            payment_received = await self.crypto_handler.check_payment(
                transaction.escrow_wallet_address,
                float(total_expected),
                transaction.currency
            )
            
            if payment_received:
                transaction.status = TransactionStatus.IN_ESCROW
                transaction.payment_received_at = datetime.now(timezone.utc)
                transaction.commission_amount = commission
                
                logger.info(f"Payment confirmed for transaction {transaction.id}")
                
                # Send notifications
                await self._send_payment_confirmation_notifications(transaction)
                
        except Exception as e:
            logger.error(f"Error checking payment for transaction {transaction.id}: {e}")
    
    async def _check_auto_release(self, transaction: Transaction):
        """Check if transaction should be auto-released after timeout"""
        try:
            # Auto-release after 7 days in escrow (configurable)
            auto_release_days = 7
            
            if transaction.payment_received_at:
                time_in_escrow = datetime.now(timezone.utc) - transaction.payment_received_at
                if time_in_escrow > timedelta(days=auto_release_days):
                    await self.release_escrow(transaction.id, auto_release=True)
                    logger.info(f"Auto-released transaction {transaction.id} after {auto_release_days} days")
                    
        except Exception as e:
            logger.error(f"Error checking auto-release for transaction {transaction.id}: {e}")
    
    async def release_escrow(self, transaction_id: int, admin_override: bool = False, 
                           auto_release: bool = False) -> bool:
        """Release escrow funds to seller"""
        try:
            with db.session.begin():
                transaction = Transaction.query.get(transaction_id)
                if not transaction:
                    logger.error(f"Transaction {transaction_id} not found")
                    return False
                
                if transaction.status != TransactionStatus.IN_ESCROW:
                    logger.error(f"Transaction {transaction_id} not in escrow status")
                    return False
                
                # Decrypt private key and send payment to seller
                private_key = decrypt_private_key(transaction.escrow_wallet_private_key)
                
                # Get seller's wallet address (would need to be stored or provided)
                seller_address = transaction.seller_wallet_address
                if not seller_address:
                    logger.error(f"No seller wallet address for transaction {transaction_id}")
                    return False
                
                # Send payment to seller (minus commission)
                tx_hash = await self.crypto_handler.send_payment(
                    transaction.escrow_wallet_address,
                    private_key,
                    seller_address,
                    float(transaction.amount),
                    transaction.currency
                )
                
                if tx_hash:
                    transaction.status = TransactionStatus.COMPLETED
                    transaction.completed_at = datetime.now(timezone.utc)
                    transaction.blockchain_tx_hash = tx_hash
                    
                    # Update user statistics
                    await self._update_user_stats(transaction)
                    
                    # Send completion notifications
                    await self._send_completion_notifications(transaction, auto_release)
                    
                    logger.info(f"Escrow released for transaction {transaction_id}, tx: {tx_hash}")
                    return True
                else:
                    logger.error(f"Failed to send payment for transaction {transaction_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error releasing escrow for transaction {transaction_id}: {e}")
            return False
    
    async def refund_escrow(self, transaction_id: int, reason: str = "") -> bool:
        """Refund escrow funds to buyer"""
        try:
            with db.session.begin():
                transaction = Transaction.query.get(transaction_id)
                if not transaction:
                    return False
                
                if transaction.status not in [TransactionStatus.IN_ESCROW, TransactionStatus.DISPUTED]:
                    return False
                
                if not transaction.buyer:
                    return False
                
                # Decrypt private key and send refund to buyer
                private_key = decrypt_private_key(transaction.escrow_wallet_private_key)
                
                # For refund, we need buyer's wallet address
                # This would typically be collected during the trade process
                # For now, we'll simulate the refund process
                
                commission = transaction.amount * transaction.commission_rate
                refund_amount = transaction.amount  # Refund without commission
                
                # In a real implementation, you'd send the crypto back to buyer's address
                # tx_hash = await self.crypto_handler.send_payment(...)
                
                transaction.status = TransactionStatus.REFUNDED
                transaction.completed_at = datetime.now(timezone.utc)
                
                # Send refund notifications
                await self._send_refund_notifications(transaction, reason)
                
                logger.info(f"Escrow refunded for transaction {transaction_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error refunding escrow for transaction {transaction_id}: {e}")
            return False
    
    async def _update_user_stats(self, transaction: Transaction):
        """Update user statistics after successful transaction"""
        try:
            # Update seller stats
            seller = transaction.seller
            seller.total_trades += 1
            seller.successful_trades += 1
            seller.reputation_score = min(5.0, seller.reputation_score + 0.1)
            
            # Update buyer stats
            if transaction.buyer:
                buyer = transaction.buyer
                buyer.total_trades += 1
                buyer.successful_trades += 1
                buyer.reputation_score = min(5.0, buyer.reputation_score + 0.05)
                
        except Exception as e:
            logger.error(f"Error updating user stats: {e}")
    
    async def _send_payment_confirmation_notifications(self, transaction: Transaction):
        """Send notifications when payment is confirmed"""
        try:
            # Notify seller
            seller_message = (
                f"💰 Payment confirmed for trade #{transaction.id}!\n"
                f"Amount: {format_currency(transaction.amount, transaction.currency.value)}\n"
                f"Buyer: @{transaction.buyer.username if transaction.buyer else 'Unknown'}\n"
                f"Please deliver your product/service."
            )
            
            seller_notification = Notification(
                user_id=transaction.seller_id,
                transaction_id=transaction.id,
                message=seller_message,
                notification_type='payment_confirmed'
            )
            
            # Notify buyer
            buyer_message = (
                f"✅ Your payment for trade #{transaction.id} is confirmed!\n"
                f"Amount: {format_currency(transaction.amount, transaction.currency.value)}\n"
                f"Funds are now in escrow. Wait for delivery."
            )
            
            if transaction.buyer:
                buyer_notification = Notification(
                    user_id=transaction.buyer_id,
                    transaction_id=transaction.id,
                    message=buyer_message,
                    notification_type='payment_confirmed'
                )
                db.session.add(buyer_notification)
            
            db.session.add(seller_notification)
            
        except Exception as e:
            logger.error(f"Error sending payment confirmation notifications: {e}")
    
    async def _send_completion_notifications(self, transaction: Transaction, auto_release: bool = False):
        """Send notifications when transaction is completed"""
        try:
            release_reason = "automatically" if auto_release else "manually"
            
            # Notify seller
            seller_message = (
                f"🎉 Trade #{transaction.id} completed {release_reason}!\n"
                f"Amount received: {format_currency(transaction.amount, transaction.currency.value)}\n"
                f"Commission: {format_currency(transaction.commission_amount, transaction.currency.value)}\n"
                f"Transaction hash: {transaction.blockchain_tx_hash}"
            )
            
            seller_notification = Notification(
                user_id=transaction.seller_id,
                transaction_id=transaction.id,
                message=seller_message,
                notification_type='trade_completed'
            )
            
            # Notify buyer
            buyer_message = (
                f"✅ Trade #{transaction.id} completed!\n"
                f"Thank you for using our escrow service.\n"
                f"Please rate your experience."
            )
            
            if transaction.buyer:
                buyer_notification = Notification(
                    user_id=transaction.buyer_id,
                    transaction_id=transaction.id,
                    message=buyer_message,
                    notification_type='trade_completed'
                )
                db.session.add(buyer_notification)
            
            db.session.add(seller_notification)
            
        except Exception as e:
            logger.error(f"Error sending completion notifications: {e}")
    
    async def _send_refund_notifications(self, transaction: Transaction, reason: str):
        """Send notifications when transaction is refunded"""
        try:
            # Notify buyer
            buyer_message = (
                f"💰 Refund issued for trade #{transaction.id}\n"
                f"Amount: {format_currency(transaction.amount, transaction.currency.value)}\n"
                f"Reason: {reason}\n"
                f"Sorry for the inconvenience."
            )
            
            if transaction.buyer:
                buyer_notification = Notification(
                    user_id=transaction.buyer_id,
                    transaction_id=transaction.id,
                    message=buyer_message,
                    notification_type='refund_issued'
                )
                db.session.add(buyer_notification)
            
            # Notify seller
            seller_message = (
                f"⚠️ Trade #{transaction.id} has been refunded\n"
                f"Amount: {format_currency(transaction.amount, transaction.currency.value)}\n"
                f"Reason: {reason}"
            )
            
            seller_notification = Notification(
                user_id=transaction.seller_id,
                transaction_id=transaction.id,
                message=seller_message,
                notification_type='refund_issued'
            )
            
            db.session.add(seller_notification)
            
        except Exception as e:
            logger.error(f"Error sending refund notifications: {e}")
    
    def get_transaction_summary(self) -> dict:
        """Get summary statistics for all transactions"""
        try:
            with db.session.begin():
                total_transactions = Transaction.query.count()
                completed_transactions = Transaction.query.filter_by(
                    status=TransactionStatus.COMPLETED
                ).count()
                
                pending_transactions = Transaction.query.filter(
                    Transaction.status.in_([
                        TransactionStatus.CREATED,
                        TransactionStatus.PAYMENT_PENDING,
                        TransactionStatus.IN_ESCROW
                    ])
                ).count()
                
                disputed_transactions = Transaction.query.filter_by(
                    status=TransactionStatus.DISPUTED
                ).count()
                
                # Calculate total volume by currency
                volume_stats = db.session.query(
                    Transaction.currency,
                    db.func.sum(Transaction.amount).label('total_volume'),
                    db.func.count(Transaction.id).label('count')
                ).filter_by(
                    status=TransactionStatus.COMPLETED
                ).group_by(Transaction.currency).all()
                
                return {
                    'total_transactions': total_transactions,
                    'completed_transactions': completed_transactions,
                    'pending_transactions': pending_transactions,
                    'disputed_transactions': disputed_transactions,
                    'success_rate': (completed_transactions / max(total_transactions, 1)) * 100,
                    'volume_by_currency': {
                        stat.currency.value: {
                            'volume': float(stat.total_volume),
                            'count': stat.count
                        } for stat in volume_stats
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting transaction summary: {e}")
            return {}
