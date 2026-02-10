# inventory/views.py

import csv
import json
import uuid
import io
from datetime import timedelta, datetime
from decimal import Decimal

# External Libraries for Exporting
from openpyxl import Workbook
from docx import Document
from docx.shared import Inches

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Q, F, Sum, Count, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import TruncDate, TruncDay, TruncHour, TruncMinute
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from django.db import models

# DRF & Swagger Imports
from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

# Local Imports
from core.cache_utils import clear_dashboard_cache
from .forms import (
    ProductCreateForm, ProductUpdateForm, StockTransactionForm, ProductFilterForm,
    TransactionFilterForm, TransactionReportForm, ProductHistoryFilterForm,
    CategoryCreateForm, PurchaseOrderFilterForm, StockOutForm, AnalyticsFilterForm,
    RefundForm, CustomerForm, CustomerPaymentForm
)
from .models import (
    Product, StockTransaction, Category, PurchaseOrder, Supplier, 
    POSSale, Customer, CustomerPayment
)
from .serializers import ProductSerializer, CategorySerializer
from .utils import render_to_pdf

# --- AUTHENTICATION ---

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.username}!")
        return response

# --- CUSTOMER & BILLING MANAGEMENT ---

class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'inventory/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        qs = Customer.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q))
        return qs

class CustomerCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'inventory/customer_form.html'
    success_url = reverse_lazy('inventory:customer_list')
    success_message = "Customer profile for '%(name)s' created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Add New Customer"
        return context

class CustomerUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'inventory/customer_form.html'
    success_message = "Customer profile for '%(name)s' updated successfully."
    
    def get_success_url(self):
        return reverse_lazy('inventory:customer_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit: {self.object.name}"
        return context

class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'inventory/customer_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object
        
        # 1. Fetch Sales (Credit)
        sales = list(customer.purchases.filter(payment_method='CREDIT').annotate(
            txn_type=Value('INVOICE', output_field=models.CharField())
        ).values('timestamp', 'receipt_id', 'total_amount', 'txn_type'))
        
        # 2. Fetch Payments
        payments = list(customer.payments.annotate(
            txn_type=Value('PAYMENT', output_field=models.CharField())
        ).values('payment_date', 'reference_number', 'amount', 'txn_type'))
        
        # 3. Combine and Normalize
        ledger = []
        for s in sales:
            ledger.append({
                'date': s['timestamp'],
                'ref': s['receipt_id'],
                'description': 'Credit Purchase',
                'debit': s['total_amount'],
                'credit': 0,
                'type': 'SALE'
            })
        for p in payments:
             ledger.append({
                'date': p['payment_date'],
                'ref': p['reference_number'],
                'description': 'Payment Received',
                'debit': 0,
                'credit': p['amount'],
                'type': 'PAYMENT'
            })
            
        # 4. Sort by date
        ledger.sort(key=lambda x: x['date'])
        
        # 5. Calculate Running Balance
        balance = 0
        for entry in ledger:
            balance += (entry['debit'] - entry['credit'])
            entry['balance'] = balance
            
        context['ledger'] = ledger
        
        # Add payment form and financial summary to context
        context['payment_form'] = CustomerPaymentForm()
        current_balance = self.object.get_balance()
        credit_limit = self.object.credit_limit
        context['current_balance'] = current_balance
        context['available_credit'] = credit_limit - current_balance
        return context

@login_required
@require_POST
def customer_payment(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerPaymentForm(request.POST)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.customer = customer
        payment.recorded_by = request.user
        payment.save()
        messages.success(request, "Payment recorded successfully.")
    else:
        messages.error(request, "Error recording payment.")
    return redirect('inventory:customer_detail', pk=pk)

@login_required
def import_customers(request):
    """Simple CSV Import for Customers"""
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a CSV file.")
            return redirect('inventory:customer_list')

        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            count = 0
            for row in reader:
                # Expects columns: name, email, phone, address
                if row.get('name'):
                    Customer.objects.get_or_create(
                        name=row.get('name'),
                        defaults={
                            'email': row.get('email', ''),
                            'phone': row.get('phone', ''),
                            'address': row.get('address', ''),
                            'tax_id': row.get('tax_id', ''),
                        }
                    )
                    count += 1
            messages.success(request, f"Successfully imported/updated {count} customers.")
        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            
        return redirect('inventory:customer_list')
        
    return render(request, 'inventory/customer_import.html')

@login_required
def import_ledger_entries(request, pk):
    """Import Ledger Entries (Charges/Payments) from CSV"""
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a CSV file.")
            return redirect('inventory:customer_detail', pk=pk)

        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            # Normalize headers (strip spaces, lowercase)
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
            
            # Expected headers mapping (naive)
            # We expect: date, reference, description, charge, payment
            
            count_charges = 0
            count_payments = 0
            
            with transaction.atomic():
                for row in reader:
                    # Parse Date
                    date_str = row.get('date')
                    try:
                        txn_date = datetime.strptime(date_str, '%Y-%m-%d')
                        txn_date = timezone.make_aware(txn_date)
                    except (ValueError, TypeError):
                        # Skip if no valid date
                        continue
                        
                    ref = row.get('reference') or ''
                    desc = row.get('description') or ''
                    
                    # Parse Amounts
                    try:
                        charge_val = float(row.get('charge') or 0)
                        payment_val = float(row.get('payment') or 0)
                    except ValueError:
                        continue
                        
                    # 1. Handle CHARGE (Debit) -> Create POSSale (Credit Sale)
                    if charge_val > 0:
                        # Check duplicate by receipt_id
                        if not POSSale.objects.filter(receipt_id=ref).exists():
                            POSSale.objects.create(
                                receipt_id=ref, # Use CSV Ref as Receipt ID
                                customer=customer,
                                payment_method='CREDIT',
                                total_amount=Decimal(charge_val),
                                amount_paid=0,
                                change_given=0,
                                timestamp=txn_date,
                                notes=desc, # Store description in notes
                                cashier=request.user
                            )
                            count_charges += 1
                            
                    # 2. Handle PAYMENT (Credit) -> Create CustomerPayment
                    if payment_val > 0:
                        # Check duplicate logic could be tricky for payments as Ref is not unique
                        # We will try to avoid exact duplicates (same date, same ref, same amount)
                        if not CustomerPayment.objects.filter(
                            customer=customer, 
                            reference_number=ref, 
                            amount=Decimal(payment_val),
                            payment_date=txn_date
                        ).exists():
                            CustomerPayment.objects.create(
                                customer=customer,
                                amount=Decimal(payment_val),
                                payment_date=txn_date,
                                reference_number=ref,
                                notes=desc,
                                recorded_by=request.user
                            )
                            count_payments += 1
                            
            messages.success(request, f"Imported {count_charges} charges and {count_payments} payments.")
            
        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            
        return redirect('inventory:customer_detail', pk=pk)

    return render(request, 'inventory/ledger_import.html', {'customer': customer})

# --- BILLING STATEMENT EXPORT (Word, Excel, PDF, CSV) ---

@login_required
def export_statement(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    format_type = request.GET.get('format', 'pdf')
    
    # --- DATA PREPARATION ---
    sales = customer.purchases.filter(payment_method='CREDIT')
    payments = customer.payments.all()
    
    ledger_items = []
    for s in sales:
        ledger_items.append({
            'date': s.timestamp, 
            'ref': s.receipt_id, 
            'desc': 'Charge (Credit Sale)', 
            'amount': s.total_amount, 
            'is_credit': False # Debit column
        })
    for p in payments:
        ledger_items.append({
            'date': p.payment_date, 
            'ref': p.reference_number, 
            'desc': 'Payment Received', 
            'amount': p.amount, 
            'is_credit': True # Credit column
        })
    
    ledger_items.sort(key=lambda x: x['date'])
    
    running_balance = 0
    final_data = []
    for item in ledger_items:
        if item['is_credit']:
            running_balance -= item['amount']
        else:
            running_balance += item['amount']
        item['balance'] = running_balance
        final_data.append(item)

    filename = f"Statement_{slugify(customer.name)}_{timezone.now().strftime('%Y%m%d')}"

    # 1. CSV EXPORT
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Date', 'Reference', 'Description', 'Charge', 'Payment', 'Balance'])
        for row in final_data:
            charge = row['amount'] if not row['is_credit'] else ''
            pay = row['amount'] if row['is_credit'] else ''
            writer.writerow([row['date'].strftime('%Y-%m-%d'), row['ref'], row['desc'], charge, pay, row['balance']])
        return response

    # 2. EXCEL EXPORT
    elif format_type == 'excel':
        wb = Workbook()
        ws = wb.active
        ws.title = "Statement"
        
        ws.append(["BILLING STATEMENT"])
        ws.append([f"Customer: {customer.name}"])
        ws.append([f"Date: {timezone.now().strftime('%Y-%m-%d')}"])
        ws.append([]) # spacer
        
        headers = ['Date', 'Reference', 'Description', 'Charge', 'Payment', 'Balance']
        ws.append(headers)
        
        for row in final_data:
            charge = row['amount'] if not row['is_credit'] else None
            pay = row['amount'] if row['is_credit'] else None
            ws.append([
                row['date'].strftime('%Y-%m-%d'), 
                row['ref'], 
                row['desc'], 
                charge, 
                pay, 
                row['balance']
            ])
            
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        wb.save(response)
        return response

    # 3. WORD EXPORT
    elif format_type == 'word':
        document = Document()
        document.add_heading(f'Billing Statement', 0)
        
        p = document.add_paragraph()
        p.add_run(f'Customer: {customer.name}\n').bold = True
        p.add_run(f'Address: {customer.address}\n')
        p.add_run(f'Date Generated: {timezone.now().strftime("%B %d, %Y")}')

        table = document.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Date'
        hdr_cells[1].text = 'Description'
        hdr_cells[2].text = 'Amount'
        hdr_cells[3].text = 'Balance'
        
        for row in final_data:
            row_cells = table.add_row().cells
            row_cells[0].text = row['date'].strftime('%Y-%m-%d')
            row_cells[1].text = f"{row['desc']} ({row['ref']})"
            
            amt_str = f"{row['amount']:,.2f}"
            if row['is_credit']:
                amt_str = f"({amt_str})" # Parenthesis for payments
                
            row_cells[2].text = amt_str
            row_cells[3].text = f"{row['balance']:,.2f}"

        # Footer total
        document.add_paragraph(f"\nTotal Outstanding Balance: {running_balance:,.2f}")

        f = io.BytesIO()
        document.save(f)
        f.seek(0)
        response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="{filename}.docx"'
        return response

    # 4. PDF EXPORT (Default)
    else:
        context = {
            'customer': customer,
            'ledger': final_data,
            'today': timezone.now(),
            'current_balance': running_balance
        }
        pdf = render_to_pdf('inventory/statement_pdf.html', context, request=request)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
            return response
        return HttpResponse("Error Generating PDF", status=500)

# --- PRODUCT MANAGEMENT (UI) ---

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    context_object_name = 'product_list'
    template_name = 'inventory/product_list.html'
    paginate_by = 12
    permission_required = 'inventory.view_product'

    def get_queryset(self):
        queryset = Product.objects.select_related('category').all()
        form = ProductFilterForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('q')
            if query:
                queryset = queryset.filter(Q(name__icontains=query) | Q(sku__icontains=query))
            category = form.cleaned_data.get('category')
            if category:
                queryset = queryset.filter(category=category)
            product_status = form.cleaned_data.get('product_status')
            if product_status:
                queryset = queryset.filter(status=product_status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProductFilterForm(self.request.GET)
        context['category_form'] = CategoryCreateForm()
        return context

class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'
    permission_required = 'inventory.view_product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = StockTransaction.objects.filter(product=self.object).order_by('-timestamp')[:10]
        context['transaction_form'] = StockOutForm()
        context['refund_form'] = RefundForm()
        return context
    
    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            product_object = Product.objects.select_for_update().get(pk=self.get_object().pk)
            form = StockOutForm(request.POST)
            
            if form.is_valid():
                transaction_obj = form.save(commit=False)
                transaction_obj.product = product_object
                transaction_obj.user = request.user
                transaction_obj.transaction_type = 'OUT'
                
                quantity = form.cleaned_data.get('quantity')
                if product_object.quantity < quantity:
                    messages.error(request, f'Cannot stock out more than available ({product_object.quantity}).')
                    return redirect(product_object.get_absolute_url())
                
                product_object.quantity -= quantity
                product_object.save()
                
                transaction_obj.selling_price = product_object.price if transaction_obj.transaction_reason == 'SALE' else None
                transaction_obj.save()
                messages.success(request, "Stock Out recorded successfully.")
            else:
                messages.error(request, "Error recording transaction.")
        return redirect(product_object.get_absolute_url())

@login_required
@require_POST
@permission_required('inventory.can_adjust_stock', raise_exception=True)
def product_refund(request, slug):
    product = get_object_or_404(Product, slug=slug)
    form = RefundForm(request.POST)
    
    if form.is_valid():
        with transaction.atomic():
            quantity = form.cleaned_data['quantity']
            StockTransaction.objects.create(
                product=product,
                transaction_type='IN',
                transaction_reason=StockTransaction.TransactionReason.RETURN,
                quantity=quantity,
                user=request.user,
                selling_price=product.price, 
                notes=f"Refund/Return: {form.cleaned_data.get('notes')}"
            )
            product.quantity += quantity
            product.save()
            messages.success(request, f"Refund processed. {quantity} items returned.")
    return redirect(product.get_absolute_url())

class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Product
    form_class = ProductCreateForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')
    success_message = "Product was created successfully!"
    permission_required = 'inventory.add_product'

class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    form_class = ProductUpdateForm
    template_name = 'inventory/product_form.html'
    success_message = "Product was updated successfully!"
    permission_required = 'inventory.change_product'
    
    def get_success_url(self):
        return self.object.get_absolute_url()

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.delete_product'

# --- POINT OF SALE (POS) SYSTEM ---

@login_required
@permission_required('inventory.can_adjust_stock', raise_exception=True)
def pos_dashboard(request):
    # Products
    active_products = Product.objects.filter(status=Product.Status.ACTIVE, quantity__gt=0).values(
        'id', 'name', 'sku', 'price', 'quantity', 'category__name'
    )
    products_json = json.dumps(list(active_products), cls=DjangoJSONEncoder)
    
    # Customers
    customers = Customer.objects.values('id', 'name', 'credit_limit')
    customers_json = json.dumps(list(customers), cls=DjangoJSONEncoder)
    
    context = {
        'page_title': 'Point of Sale',
        'products_json': products_json,
        'customers_json': customers_json,
    }
    return render(request, 'inventory/pos.html', context)

@login_required
@require_POST
def pos_checkout(request):
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        
        # New: Customer and Payment Method Logic
        customer_id = data.get('customer_id') 
        payment_method = data.get('payment_method', 'CASH') # CASH, CREDIT, CARD
        
        raw_amount = data.get('amount_paid')
        amount_paid = Decimal(str(raw_amount)) if raw_amount else Decimal('0')

        if not items:
            return JsonResponse({'status': 'error', 'message': 'Cart is empty'}, status=400)

        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(pk=customer_id)
            except Customer.DoesNotExist:
                pass

        # Calculate Total Cost first to validate Credit Limit
        total_calculated_cost = Decimal('0')
        item_objects = []
        
        # Pre-validation Loop
        for item in items:
            product = Product.objects.get(pk=item.get('id'))
            qty = int(item.get('qty'))
            if product.quantity < qty:
                raise ValueError(f"Insufficient stock for {product.name}")
            total_calculated_cost += (product.price * qty)
            item_objects.append({'product': product, 'qty': qty})

        # Credit Validation
        if payment_method == 'CREDIT':
            if not customer:
                 return JsonResponse({'status': 'error', 'message': 'Customer required for credit sales'}, status=400)
            
            current_balance = customer.get_balance()
            if customer.credit_limit > 0 and (current_balance + total_calculated_cost) > customer.credit_limit:
                 return JsonResponse({'status': 'error', 'message': f'Credit limit exceeded. Available: {customer.credit_limit - current_balance}'}, status=400)
            
            # If credit, immediate payment is 0
            amount_paid = Decimal('0') 
        elif payment_method == 'CASH':
             if amount_paid < total_calculated_cost:
                 raise ValueError("Amount paid is less than total amount.")

        receipt_id = f"REC-{uuid.uuid4().hex[:8].upper()}"
        
        with transaction.atomic():
            # 1. Create Sale Header
            sale_record = POSSale.objects.create(
                receipt_id=receipt_id,
                cashier=request.user,
                customer=customer,
                payment_method=payment_method,
                total_amount=total_calculated_cost, 
                amount_paid=amount_paid,
                change_given=(amount_paid - total_calculated_cost) if payment_method == 'CASH' else 0
            )

            receipt_items_response = []
            
            # 2. Process Items
            for item_obj in item_objects:
                product = item_obj['product']
                sell_qty = item_obj['qty']
                
                # Lock row
                product = Product.objects.select_for_update().get(pk=product.id)
                product.quantity -= sell_qty
                product.save()
                
                sell_price = product.price
                line_total = sell_qty * sell_price
                
                StockTransaction.objects.create(
                    product=product,
                    transaction_type='OUT',
                    transaction_reason=StockTransaction.TransactionReason.SALE,
                    quantity=sell_qty,
                    selling_price=sell_price,
                    user=request.user,
                    pos_sale=sale_record,
                    notes=f"POS Sale: {receipt_id} ({payment_method})"
                )
                
                receipt_items_response.append({
                    'name': product.name,
                    'qty': sell_qty,
                    'price': f"{sell_price:,.2f}",
                    'total': f"{line_total:,.2f}"
                })

            return JsonResponse({
                'status': 'success', 
                'receipt_id': receipt_id,
                'date': sale_record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'customer_name': customer.name if customer else 'Walk-in',
                'items': receipt_items_response,
                'total': f"{total_calculated_cost:,.2f}",
                'amount_paid': f"{amount_paid:,.2f}",
                'change': f"{sale_record.change_given:,.2f}"
            })

    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class POSHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = POSSale
    template_name = 'inventory/pos_history.html'
    context_object_name = 'sales'
    paginate_by = 20
    permission_required = 'inventory.view_stocktransaction'
    
    def get_queryset(self):
        return POSSale.objects.select_related('cashier', 'customer').order_by('-timestamp')

class POSReceiptDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = POSSale
    template_name = 'inventory/pos_receipt.html'
    context_object_name = 'sale'
    permission_required = 'inventory.view_stocktransaction'
    
    def get_object(self):
        return get_object_or_404(POSSale, receipt_id=self.kwargs['receipt_id'])

# --- ANALYTICS & REPORTS ---

@method_decorator(xframe_options_exempt, name='dispatch')
class ReportingView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'inventory/reporting.html'
    permission_required = 'inventory.can_view_reports'
    
    def get(self, request, *args, **kwargs):
        export_type = request.GET.get('export')
        if export_type == 'inventory_csv': return self.export_inventory_csv()
        elif export_type == 'transaction_pdf': return self.export_transactions_pdf(request)
        return super().get(request, *args, **kwargs)

    # ... (Keep existing export methods for Inventory/Transactions) ...
    def export_inventory_csv(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory.csv"'
        writer = csv.writer(response)
        writer.writerow(['Product', 'SKU', 'Qty', 'Price'])
        for p in Product.objects.all():
            writer.writerow([p.name, p.sku, p.quantity, p.price])
        return response

    def export_transactions_pdf(self, request):
        # Implementation assumed from previous context
        return HttpResponse("PDF Report")

@login_required
def analytics_dashboard(request):
    # 1. Date Filtering
    initial_start = timezone.now().date() - timedelta(days=30)
    initial_end = timezone.now().date()
    
    start_date = initial_start
    end_date = initial_end
    
    if 'start_date' in request.GET:
        filter_form = AnalyticsFilterForm(request.GET)
        if filter_form.is_valid():
            start_date = filter_form.cleaned_data.get('start_date') or initial_start
            end_date = filter_form.cleaned_data.get('end_date') or initial_end
    else:
        filter_form = AnalyticsFilterForm(initial={'start_date': initial_start, 'end_date': initial_end})

    # Make end_date inclusive (end of the day)
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    # 2. Base Querysets
    pos_sales = POSSale.objects.filter(timestamp__range=[start_dt, end_dt])
    stock_txns = StockTransaction.objects.filter(timestamp__range=[start_dt, end_dt])
    
    # 3. KPI Calculations
    total_revenue = pos_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    
    total_refunds_val = stock_txns.filter(
        transaction_type='IN', 
        transaction_reason=StockTransaction.TransactionReason.RETURN
    ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

    gross_sales = total_revenue + total_refunds_val
    
    total_units = stock_txns.filter(
        transaction_type='OUT', 
        transaction_reason=StockTransaction.TransactionReason.SALE
    ).aggregate(qty=Sum('quantity'))['qty'] or 0
    
    total_loss = stock_txns.filter(
        transaction_reason=StockTransaction.TransactionReason.DAMAGE
    ).aggregate(val=Sum(F('quantity') * F('product__price')))['val'] or 0

    # 4. Chart Data Preparation
    # A. Sales by Category
    cat_qs = stock_txns.filter(
        transaction_type='OUT', transaction_reason=StockTransaction.TransactionReason.SALE
    ).values('product__category__name').annotate(sales=Sum(F('quantity') * F('selling_price'))).order_by('-sales')
    
    cat_labels = [item['product__category__name'] or 'Uncategorized' for item in cat_qs]
    cat_values = [float(item['sales']) for item in cat_qs]
    
    # B. Top 5 Best Selling Products
    prod_qs = stock_txns.filter(
        transaction_type='OUT', transaction_reason=StockTransaction.TransactionReason.SALE
    ).values('product__name').annotate(sales=Sum(F('quantity') * F('selling_price'))).order_by('-sales')[:5]
    
    prod_labels = [item['product__name'] for item in prod_qs]
    prod_values = [float(item['sales']) for item in prod_qs]
    
    # C. Daily Sales Trend
    trend_qs = pos_sales.annotate(date=TruncDate('timestamp')).values('date').annotate(daily_total=Sum('total_amount')).order_by('date')
    
    date_labels = [item['date'].strftime('%b %d') for item in trend_qs]
    date_values = [float(item['daily_total']) for item in trend_qs]

    context = {
        'filter_form': filter_form,
        'start_date': start_date,
        'end_date': end_date,
        
        # KPIs
        'total_revenue': total_revenue,
        'gross_sales': gross_sales,
        'total_units': total_units,
        'total_refunds': total_refunds_val,
        'total_loss': total_loss,
        
        # Charts (JSON)
        'cat_labels': json.dumps(cat_labels),
        'cat_values': json.dumps(cat_values),
        'prod_labels': json.dumps(prod_labels),
        'prod_values': json.dumps(prod_values),
        'date_labels': json.dumps(date_labels),
        'date_values': json.dumps(date_values),
    }
    return render(request, 'inventory/analytics.html', context)

# --- PURCHASE ORDERS & SUPPLIERS (Existing) ---

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'inventory/purchaseorder_list.html'
    context_object_name = 'po_list'
    paginate_by = 20
    permission_required = 'inventory.view_purchaseorder'
    
    def get_queryset(self):
        return PurchaseOrder.objects.select_related('supplier').order_by('-order_date')

class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'inventory/purchaseorder_detail.html'
    context_object_name = 'po'
    permission_required = 'inventory.view_purchaseorder'

@login_required
@permission_required('inventory.change_purchaseorder', raise_exception=True)
def receive_purchase_order(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST' and po.status == 'COMPLETED':
        po.complete_order(request.user)
        messages.success(request, f"Stock from PO #{po.id} added.")
    return redirect('inventory:purchaseorder_list')

class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'inventory/supplier_list.html'

class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = 'inventory/supplier_detail.html'

# --- API VIEWS (DRF) ---

@extend_schema(tags=['Inventory Management'])
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

# --- AJAX HELPERS ---

@login_required
@require_POST
def add_category_ajax(request):
    form = CategoryCreateForm(request.POST)
    if form.is_valid():
        cat = form.save()
        return JsonResponse({'status': 'success', 'category': {'id': cat.id, 'name': cat.name}})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def sales_chart_data(request):
    period = request.GET.get('period', 'hour')
    now = timezone.now()

    if period == 'minute':
        # Last hour, grouped by minute
        start_time = now - timedelta(hours=1)
        trunc_func = TruncMinute('timestamp')
        date_format = '%H:%M'
    elif period == 'hour':
        # Last 24 hours, grouped by hour
        start_time = now - timedelta(hours=24)
        trunc_func = TruncHour('timestamp')
        date_format = '%I %p'
    else:
        # Last 30 days, grouped by day
        start_time = now - timedelta(days=30)
        trunc_func = TruncDate('timestamp')
        date_format = '%b %d'

    # Aggregate sales data
    sales_data = StockTransaction.objects.filter(
        transaction_type='OUT',
        transaction_reason=StockTransaction.TransactionReason.SALE,
        timestamp__gte=start_time,
        selling_price__isnull=False
    ).annotate(period_group=trunc_func).values('period_group').annotate(
        total_sales=Sum(F('selling_price') * F('quantity'))
    ).order_by('period_group')
    
    labels = [entry['period_group'].strftime(date_format) for entry in sales_data]
    data = [float(entry['total_sales']) for entry in sales_data]
    
    return JsonResponse({'labels': labels, 'data': data})

# --- MISSING UTILITY VIEWS ---

@require_POST
@permission_required('inventory.change_product', raise_exception=True)
def product_toggle_status(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if product.status == Product.Status.ACTIVE:
        product.status = Product.Status.DEACTIVATED
        messages.success(request, f"'{product.name}' has been deactivated.")
    else:
        product.status = Product.Status.ACTIVE
        messages.success(request, f"'{product.name}' has been activated.")
    product.save()
    return redirect(product.get_absolute_url())

class TransactionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = StockTransaction
    template_name = 'inventory/transaction_list.html'
    context_object_name = 'transaction_list'
    paginate_by = 25
    permission_required = 'inventory.view_stocktransaction'
    
    def get_queryset(self):
        queryset = StockTransaction.objects.select_related('product', 'user').all()
        form = TransactionFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('product'): queryset = queryset.filter(product=form.cleaned_data['product'])
            if form.cleaned_data.get('transaction_type'): queryset = queryset.filter(transaction_type=form.cleaned_data['transaction_type'])
            if form.cleaned_data.get('transaction_reason'): queryset = queryset.filter(transaction_reason=form.cleaned_data['transaction_reason'])
            if form.cleaned_data.get('user'): queryset = queryset.filter(user=form.cleaned_data['user'])
            if form.cleaned_data.get('start_date'): queryset = queryset.filter(timestamp__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'): queryset = queryset.filter(timestamp__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-timestamp')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = TransactionFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

class ProductHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product.history.model
    template_name = 'inventory/product_history_list.html'
    context_object_name = 'history_list'
    paginate_by = 20
    permission_required = 'inventory.can_view_history'
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('history_user')
        form = ProductHistoryFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('product'):
                queryset = queryset.filter(id=form.cleaned_data['product'].id)
            if form.cleaned_data.get('user'):
                queryset = queryset.filter(history_user=form.cleaned_data['user'])
            if form.cleaned_data.get('start_date'):
                queryset = queryset.filter(history_date__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'):
                queryset = queryset.filter(history_date__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-history_date')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProductHistoryFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

class ProductHistoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product.history.model
    template_name = 'inventory/product_history_detail.html'
    context_object_name = 'history_list'
    paginate_by = 20
    permission_required = 'inventory.can_view_history'
    
    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, slug=self.kwargs['slug'])
        return super().dispatch(request, *args, **kwargs)
        
    def get_queryset(self):
        return self.product.history.select_related('history_user').all().order_by('-history_date')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        return context