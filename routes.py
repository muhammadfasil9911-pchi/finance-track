from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from models import db, Transaction
from datetime import datetime
import csv
import io

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    
    total_income = sum(entry.amount for entry in transactions if entry.transaction_type == 'Income')
    total_expense = sum(entry.amount for entry in transactions if entry.transaction_type == 'Expense')
    net_balance = total_income - total_expense
    
    import collections
    daily_income_totals = collections.defaultdict(float)
    daily_expense_totals = collections.defaultdict(float)
    mode_distribution = collections.defaultdict(float)

    current_month = datetime.utcnow().strftime('%Y-%m')
    current_month_income = 0
    previous_month_income = 0
    current_month_expense = 0
    
    year = datetime.utcnow().year
    month = datetime.utcnow().month
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    previous_month_str = f"{prev_year}-{prev_month:02d}"

    for entry in transactions:
        date_str = entry.date.strftime('%Y-%m-%d')
        month_str = entry.date.strftime('%Y-%m')
        
        if entry.transaction_type == 'Income':
            daily_income_totals[date_str] += entry.amount
            if month_str == current_month:
                current_month_income += entry.amount
            elif month_str == previous_month_str:
                previous_month_income += entry.amount
        else:
            daily_expense_totals[date_str] += entry.amount
            mode_distribution[entry.payment_mode] += entry.amount # Track expense modes
            if month_str == current_month:
                current_month_expense += entry.amount

    growth_percentage = 0
    if previous_month_income > 0:
        growth_percentage = ((current_month_income - previous_month_income) / previous_month_income) * 100

    # Combine all dates for charts
    all_dates = sorted(list(set(daily_income_totals.keys()).union(set(daily_expense_totals.keys()))))[-30:] # last 30 active days
    
    daily_incomes = [daily_income_totals.get(d, 0) for d in all_dates]
    daily_expenses = [daily_expense_totals.get(d, 0) for d in all_dates]

    # Sort recent transactions by date descending limit 5
    recent_txs = sorted(transactions, key=lambda x: x.date, reverse=True)[:5]

    return render_template('dashboard.html', 
        net_balance=net_balance,
        total_income=total_income,
        total_expense=total_expense,
        current_month_income=current_month_income,
        current_month_expense=current_month_expense,
        growth_percentage=growth_percentage,
        recent_txs=recent_txs,
        dates=all_dates, 
        daily_incomes=daily_incomes,
        daily_expenses=daily_expenses,
        mode_labels=list(mode_distribution.keys()),
        mode_data=list(mode_distribution.values())
    )

@main_bp.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    if request.method == 'POST':
        source = request.form.get('source')
        amount = float(request.form.get('amount'))
        category = request.form.get('category')
        date_str = request.form.get('date')
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        transaction_type = request.form.get('transaction_type')
        timing_type = request.form.get('timing_type')
        payment_mode = request.form.get('payment_mode')
        
        entry = Transaction(user_id=current_user.id, source=source, amount=amount, 
                            category=category, date=date_obj, transaction_type=transaction_type,
                            timing_type=timing_type, payment_mode=payment_mode)
        db.session.add(entry)
        db.session.commit()
        flash(f'{transaction_type} entry added!', 'success')
        return redirect(url_for('main.transactions'))

    query = Transaction.query.filter_by(user_id=current_user.id)
    
    filter_tx_type = request.args.get('tx_type')
    if filter_tx_type:
        query = query.filter_by(transaction_type=filter_tx_type)
        
    filter_type = request.args.get('type')
    if filter_type:
        query = query.filter_by(timing_type=filter_type)
        
    filter_mode = request.args.get('mode')
    if filter_mode:
        query = query.filter_by(payment_mode=filter_mode)

    txs = query.order_by(Transaction.date.desc()).all()
    
    return render_template('transactions.html', transactions=txs)

@main_bp.route('/transactions/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    entry = Transaction.query.get_or_404(id)
    if entry.user_id != current_user.id:
        return redirect(url_for('main.transactions'))
        
    db.session.delete(entry)
    db.session.commit()
    flash('Transaction deleted!', 'success')
    return redirect(url_for('main.transactions'))

@main_bp.route('/export')
@login_required
def export_csv():
    txs = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Description', 'Category', 'Type', 'Amount', 'Timing', 'Payment Mode'])
    
    for entry in txs:
        writer.writerow([
            entry.date.strftime('%Y-%m-%d'),
            entry.source,
            entry.category,
            entry.transaction_type,
            entry.amount,
            entry.timing_type,
            entry.payment_mode
        ])
        
    bytes_output = io.BytesIO()
    bytes_output.write(output.getvalue().encode('utf-8'))
    bytes_output.seek(0)
    
    return send_file(bytes_output, mimetype="text/csv", download_name='transactions_export.csv', as_attachment=True)

@main_bp.route('/insights')
@login_required
def insights():
    txs = Transaction.query.filter_by(user_id=current_user.id).all()
    
    insight_messages = []
    
    expenses = [t for t in txs if t.transaction_type == 'Expense']
    incomes = [t for t in txs if t.transaction_type == 'Income']
    
    if not txs:
        insight_messages.append("Not enough data to generate reliable insights yet. Keep adding your transactions!")
    else:
        # Irregular high expense detection
        if expenses:
            amounts = [e.amount for e in expenses]
            average = sum(amounts) / len(amounts) if amounts else 0
            for entry in expenses:
                if entry.amount > average * 2.5 and average > 0:
                    insight_messages.append(f"High expense alert: {entry.date.strftime('%Y-%m-%d')} - {entry.source} (₹{entry.amount}). This is unusually high compared to your average expense of ₹{average:.0f}.")
        
        # Cashflow snapshot
        total_in = sum(e.amount for e in incomes)
        total_out = sum(e.amount for e in expenses)
        if total_out > total_in:
            insight_messages.append(f"Negative Cashflow Warning: Your total expenses (₹{total_out:.0f}) exceed your incomes (₹{total_in:.0f}). Please review your spending!")
        elif total_in > 0:
            savings_rate = ((total_in - total_out) / total_in) * 100
            insight_messages.append(f"Great job! Your overall savings rate is {savings_rate:.1f}%.")

    return render_template('insights.html', insights=insight_messages)
