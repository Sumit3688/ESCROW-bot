"""
Custom Dispute Handling System
Modify this file to customize how disputes are handled in your escrow bot
"""

from datetime import datetime, timezone, timedelta
from models import Dispute, Transaction, User, DisputeStatus, TransactionStatus
from app import db
from config import DISPUTE_CONFIG, MESSAGE_TEMPLATES, BOT_CONFIG
import logging

logger = logging.getLogger(__name__)

class CustomDisputeHandler:
    """Custom dispute handler with configurable rules"""
    
    def __init__(self):
        self.config = DISPUTE_CONFIG
        
    def create_dispute(self, transaction_id: int, user_id: int, reason: str, description: str):
        """Create a new dispute with custom validation"""
        try:
            with db.session.begin():
                # Check if transaction exists and is eligible for dispute
                transaction = Transaction.query.get(transaction_id)
                if not transaction:
                    return {'success': False, 'message': 'Transaction not found'}
                
                # Check if transaction is in a disputable state
                if transaction.status not in [TransactionStatus.IN_ESCROW, TransactionStatus.PAYMENT_RECEIVED]:
                    return {'success': False, 'message': 'Transaction cannot be disputed in current state'}
                
                # Check if user is part of this transaction
                user = User.query.get(user_id)
                if not user or (user.id != transaction.seller_id and user.id != transaction.buyer_id):
                    return {'success': False, 'message': 'You are not authorized to dispute this transaction'}
                
                # Check for existing dispute
                existing_dispute = Dispute.query.filter_by(transaction_id=transaction_id).first()
                if existing_dispute:
                    return {'success': False, 'message': 'Dispute already exists for this transaction'}
                
                # Validate dispute amount limit
                if transaction.amount > self.config['MAX_DISPUTE_AMOUNT']:
                    return {'success': False, 'message': f'Transaction amount exceeds dispute limit of ${self.config["MAX_DISPUTE_AMOUNT"]}'}
                
                # Create the dispute
                dispute = Dispute(
                    transaction_id=transaction_id,
                    initiated_by=user_id,
                    reason=reason,
                    description=description,
                    status=DisputeStatus.OPEN
                )
                
                db.session.add(dispute)
                
                # Update transaction status
                transaction.status = TransactionStatus.DISPUTED
                
                logger.info(f"Dispute created for transaction {transaction_id} by user {user_id}")
                
                return {
                    'success': True, 
                    'message': 'Dispute created successfully',
                    'dispute_id': dispute.id
                }
                
        except Exception as e:
            logger.error(f"Error creating dispute: {e}")
            return {'success': False, 'message': 'Failed to create dispute'}
    
    def auto_resolve_disputes(self):
        """Automatically resolve disputes based on your custom rules"""
        try:
            # Get disputes that are old enough for auto-resolution
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config['AUTO_RESOLVE_DAYS'])
            
            old_disputes = Dispute.query.filter(
                Dispute.status == DisputeStatus.OPEN,
                Dispute.created_at < cutoff_date
            ).all()
            
            resolved_count = 0
            
            for dispute in old_disputes:
                # Custom auto-resolution logic - you can modify this
                resolution_result = self._auto_resolve_single_dispute(dispute)
                if resolution_result['success']:
                    resolved_count += 1
            
            logger.info(f"Auto-resolved {resolved_count} disputes")
            return {'success': True, 'resolved_count': resolved_count}
            
        except Exception as e:
            logger.error(f"Error in auto-resolve disputes: {e}")
            return {'success': False, 'message': str(e)}
    
    def _auto_resolve_single_dispute(self, dispute):
        """Custom logic for resolving a single dispute"""
        try:
            transaction = dispute.transaction
            
            # CUSTOMIZE THIS LOGIC BASED ON YOUR PREFERENCES:
            
            # Example 1: Always favor the seller for small amounts
            if transaction.amount < 50:
                action = 'release'
                resolution = "Auto-resolved: Small amount dispute - funds released to seller"
            
            # Example 2: Split funds for medium amounts
            elif transaction.amount < 200:
                action = 'split'
                resolution = "Auto-resolved: Medium amount dispute - funds split between parties"
            
            # Example 3: Require manual review for large amounts
            else:
                # Don't auto-resolve large disputes
                return {'success': False, 'message': 'Large amount requires manual review'}
            
            # Apply the resolution
            with db.session.begin():
                dispute.status = DisputeStatus.RESOLVED
                dispute.resolved_by_admin = True
                dispute.resolution_notes = resolution
                dispute.resolved_at = datetime.now(timezone.utc)
                
                if action == 'release':
                    transaction.status = TransactionStatus.COMPLETED
                elif action == 'refund':
                    transaction.status = TransactionStatus.REFUNDED
                elif action == 'split':
                    # For split resolution, you might want to handle this differently
                    transaction.status = TransactionStatus.COMPLETED
                    dispute.resolution_notes += " (50/50 split - contact admin for details)"
                
                transaction.completed_at = datetime.now(timezone.utc)
            
            return {'success': True, 'action': action}
            
        except Exception as e:
            logger.error(f"Error auto-resolving dispute {dispute.id}: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_dispute_statistics(self):
        """Get dispute statistics for admin dashboard"""
        try:
            total_disputes = Dispute.query.count()
            open_disputes = Dispute.query.filter_by(status=DisputeStatus.OPEN).count()
            resolved_disputes = Dispute.query.filter_by(status=DisputeStatus.RESOLVED).count()
            
            # Calculate resolution times
            resolved_with_times = Dispute.query.filter(
                Dispute.status == DisputeStatus.RESOLVED,
                Dispute.resolved_at.isnot(None)
            ).all()
            
            avg_resolution_time = 0
            if resolved_with_times:
                total_time = sum([
                    (d.resolved_at - d.created_at).total_seconds() / 3600  # Convert to hours
                    for d in resolved_with_times
                ])
                avg_resolution_time = total_time / len(resolved_with_times)
            
            return {
                'total_disputes': total_disputes,
                'open_disputes': open_disputes,
                'resolved_disputes': resolved_disputes,
                'resolution_rate': (resolved_disputes / max(total_disputes, 1)) * 100,
                'avg_resolution_hours': round(avg_resolution_time, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting dispute statistics: {e}")
            return {
                'total_disputes': 0,
                'open_disputes': 0,
                'resolved_disputes': 0,
                'resolution_rate': 0,
                'avg_resolution_hours': 0
            }

# Singleton instance
dispute_handler = CustomDisputeHandler()