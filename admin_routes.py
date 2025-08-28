from flask import render_template, request, jsonify, redirect, url_for, flash, session
from app import app, db
from models import (Transaction, User, Dispute, Notification, SystemConfig, 
                   TransactionStatus, DisputeStatus, CryptoCurrency)
from escrow_manager import EscrowManager
from utils import format_currency, format_timestamp, is_admin_user
from sqlalchemy import desc, func
from datetime import datetime, timezone, timedelta
from config import BOT_CONFIG, DISPUTE_CONFIG, ADMIN_WALLETS
import logging

logger = logging.getLogger(__name__)
escrow_manager = EscrowManager()

@app.route('/')
def index():
    """Main landing page redirects to admin dashboard"""
    return redirect(url_for('admin_dashboard'))

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard with overview statistics"""
    # In a real application, implement proper authentication
    # For now, we'll show the dashboard to everyone
    
    try:
        # Get transaction statistics
        stats = escrow_manager.get_transaction_summary()
        
        # Recent transactions
        recent_transactions = Transaction.query.order_by(desc(Transaction.created_at)).limit(10).all()
        
        # Active disputes
        active_disputes = Dispute.query.filter_by(status=DisputeStatus.OPEN).count()
        
        # User statistics
        total_users = User.query.count()
        active_users_24h = User.query.filter(
            User.last_active > datetime.now(timezone.utc) - timedelta(hours=24)
        ).count()
        
        return render_template('admin_dashboard.html',
                             stats=stats,
                             recent_transactions=recent_transactions,
                             active_disputes=active_disputes,
                             total_users=total_users,
                             active_users_24h=active_users_24h,
                             config=BOT_CONFIG)
                             
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        # Provide default values in case of error
        default_stats = {
            'total_transactions': 0,
            'total_volume': 0,
            'pending_transactions': 0,
            'completed_transactions': 0,
            'disputed_transactions': 0,
            'total_commission': 0
        }
        flash("Error loading dashboard data", "error")
        return render_template('admin_dashboard.html',
                             stats=default_stats,
                             recent_transactions=[],
                             active_disputes=0,
                             total_users=0,
                             active_users_24h=0,
                             config=BOT_CONFIG)

@app.route('/admin/transactions')
def admin_transactions():
    """View and manage all transactions"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    currency_filter = request.args.get('currency', '')
    
    query = Transaction.query
    
    # Apply filters
    if status_filter:
        try:
            status_enum = TransactionStatus[status_filter.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            pass
    
    if currency_filter:
        try:
            currency_enum = CryptoCurrency[currency_filter.upper()]
            query = query.filter_by(currency=currency_enum)
        except KeyError:
            pass
    
    # Pagination
    transactions = query.order_by(desc(Transaction.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('transactions.html', 
                         transactions=transactions,
                         status_filter=status_filter,
                         currency_filter=currency_filter)

@app.route('/admin/users')
def admin_users():
    """View and manage users"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%'))
        )
    
    users = query.order_by(desc(User.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('users.html', 
                         users=users,
                         search=search)

@app.route('/admin/disputes')
def admin_disputes():
    """View and manage disputes"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = Dispute.query
    
    if status_filter:
        try:
            status_enum = DisputeStatus[status_filter.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            pass
    
    disputes = query.order_by(desc(Dispute.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('disputes.html', 
                         disputes=disputes,
                         status_filter=status_filter)

@app.route('/api/admin/transaction/<int:transaction_id>/release', methods=['POST'])
def release_transaction(transaction_id):
    """API endpoint to release escrow funds"""
    try:
        # For now, return a simulated success response
        # In production, this would integrate with actual blockchain operations
        with db.session.begin():
            transaction = Transaction.query.get(transaction_id)
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transaction not found'
                }), 404
            
            if transaction.status != TransactionStatus.IN_ESCROW:
                return jsonify({
                    'success': False,
                    'message': 'Transaction not in escrow status'
                }), 400
            
            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED
            transaction.completed_at = datetime.now(timezone.utc)
            
            success = True
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Transaction {transaction_id} released successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to release transaction'
            }), 400
            
    except Exception as e:
        logger.error(f"Error releasing transaction {transaction_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal error occurred'
        }), 500

@app.route('/api/admin/transaction/<int:transaction_id>/refund', methods=['POST'])
def refund_transaction(transaction_id):
    """API endpoint to refund escrow funds"""
    try:
        reason = request.json.get('reason', 'Admin refund')
        
        # For now, return a simulated success response
        with db.session.begin():
            transaction = Transaction.query.get(transaction_id)
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transaction not found'
                }), 404
            
            if transaction.status not in [TransactionStatus.IN_ESCROW, TransactionStatus.DISPUTED]:
                return jsonify({
                    'success': False,
                    'message': 'Transaction cannot be refunded'
                }), 400
            
            # Update transaction status
            transaction.status = TransactionStatus.REFUNDED
            transaction.completed_at = datetime.now(timezone.utc)
            
            success = True
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Transaction {transaction_id} refunded successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to refund transaction'
            }), 400
            
    except Exception as e:
        logger.error(f"Error refunding transaction {transaction_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal error occurred'
        }), 500

@app.route('/api/admin/dispute/<int:dispute_id>/resolve', methods=['POST'])
def resolve_dispute(dispute_id):
    """API endpoint to resolve a dispute"""
    try:
        resolution = request.json.get('resolution', '')
        action = request.json.get('action', 'release')  # 'release' or 'refund'
        
        with db.session.begin():
            dispute = Dispute.query.get(dispute_id)
            if not dispute:
                return jsonify({
                    'success': False,
                    'message': 'Dispute not found'
                }), 404
            
            # Update dispute
            dispute.status = DisputeStatus.RESOLVED
            dispute.resolved_by_admin = True
            dispute.resolution_notes = resolution
            dispute.resolved_at = datetime.now(timezone.utc)
            
            # Perform action on transaction
            if action == 'release':
                # Update transaction to completed
                dispute.transaction.status = TransactionStatus.COMPLETED
                dispute.transaction.completed_at = datetime.now(timezone.utc)
                success = True
            elif action == 'refund':
                # Update transaction to refunded
                dispute.transaction.status = TransactionStatus.REFUNDED
                dispute.transaction.completed_at = datetime.now(timezone.utc)
                success = True
            else:
                success = False
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Dispute {dispute_id} resolved with {action}'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Failed to {action} transaction'
                }), 400
                
    except Exception as e:
        logger.error(f"Error resolving dispute {dispute_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal error occurred'
        }), 500

@app.route('/api/admin/stats')
def admin_stats_api():
    """API endpoint for dashboard statistics"""
    try:
        stats = escrow_manager.get_transaction_summary()
        
        # Add time-based statistics
        now = datetime.now(timezone.utc)
        
        # Transactions in last 24 hours
        recent_transactions = Transaction.query.filter(
            Transaction.created_at > now - timedelta(hours=24)
        ).count()
        
        # Revenue in last 30 days (commission)
        monthly_revenue = db.session.query(
            func.sum(Transaction.commission_amount)
        ).filter(
            Transaction.completed_at > now - timedelta(days=30),
            Transaction.status == TransactionStatus.COMPLETED
        ).scalar() or 0
        
        stats.update({
            'recent_transactions': recent_transactions,
            'monthly_revenue': float(monthly_revenue)
        })
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

@app.route('/api/admin/user/<int:user_id>/suspend', methods=['POST'])
def suspend_user(user_id):
    """API endpoint to suspend a user"""
    try:
        with db.session.begin():
            user = User.query.get(user_id)
            if not user:
                return jsonify({
                    'success': False,
                    'message': 'User not found'
                }), 404
            
            user.status = 'suspended'
            
            return jsonify({
                'success': True,
                'message': f'User {user_id} suspended successfully'
            })
            
    except Exception as e:
        logger.error(f"Error suspending user {user_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal error occurred'
        }), 500

@app.route('/admin/settings')
def admin_settings():
    """Bot configuration settings page"""
    from crypto_handler import CryptoHandler
    crypto_handler = CryptoHandler()
    
    # Check wallet configuration status
    wallet_status = crypto_handler.validate_admin_addresses()
    
    return render_template('settings.html',
                         config=BOT_CONFIG,
                         admin_wallets=ADMIN_WALLETS,
                         dispute_config=DISPUTE_CONFIG,
                         wallet_status=wallet_status)

# Template filters
@app.template_filter('format_currency')
def format_currency_filter(amount, currency):
    """Template filter for formatting currency"""
    return format_currency(float(amount), currency)

@app.template_filter('format_timestamp')
def format_timestamp_filter(timestamp, format_type='full'):
    """Template filter for formatting timestamps"""
    return format_timestamp(timestamp, format_type)

@app.template_filter('transaction_status_badge')
def transaction_status_badge(status):
    """Template filter for transaction status badges"""
    badge_classes = {
        'created': 'badge-secondary',
        'payment_pending': 'badge-warning',
        'payment_received': 'badge-info',
        'in_escrow': 'badge-primary',
        'completed': 'badge-success',
        'disputed': 'badge-danger',
        'cancelled': 'badge-dark',
        'refunded': 'badge-warning'
    }
    
    class_name = badge_classes.get(status.value if hasattr(status, 'value') else status, 'badge-secondary')
    display_name = status.value.replace('_', ' ').title() if hasattr(status, 'value') else str(status).replace('_', ' ').title()
    
    return f'<span class="badge {class_name}">{display_name}</span>'

@app.template_filter('dispute_status_badge')
def dispute_status_badge(status):
    """Template filter for dispute status badges"""
    badge_classes = {
        'open': 'badge-danger',
        'investigating': 'badge-warning',
        'resolved': 'badge-success',
        'closed': 'badge-secondary'
    }
    
    class_name = badge_classes.get(status.value if hasattr(status, 'value') else status, 'badge-secondary')
    display_name = status.value.title() if hasattr(status, 'value') else str(status).title()
    
    return f'<span class="badge {class_name}">{display_name}</span>'
