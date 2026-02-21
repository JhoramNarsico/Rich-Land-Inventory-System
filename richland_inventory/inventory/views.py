# inventory/views.py

import csv
import json
import uuid
from datetime import timedelta, datetime
from decimal import Decimal, InvalidOperation

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Q, F, Sum, Count, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import TruncDate, Coalesce
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from django.db import models
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse
from .models import (
    Customer, HydraulicSow, Expense, ExpenseCategory, Product, StockTransaction, 
    Category, PurchaseOrder, Supplier, POSSale, CustomerPayment, PurchaseOrderItem
)
from .forms import (
    ExpenseFilterForm, ExpenseForm, ProductCreateForm, ProductUpdateForm, 
    StockTransactionForm, ProductFilterForm, TransactionFilterForm, 
    TransactionReportForm, ProductHistoryFilterForm, CategoryCreateForm, 
    PurchaseOrderFilterForm, StockOutForm, AnalyticsFilterForm, RefundForm, 
    CustomerForm, CustomerPaymentForm, CustomerFilterForm
)
from .utils import render_to_pdf
from .exports import (
    generate_sow_history_export, generate_expense_report, generate_customer_list_export,
    generate_customer_statement, generate_inventory_csv, generate_supplier_deliveries_export
)
from openpyxl import load_workbook # Kept for imports
from core.cache_utils import clear_dashboard_cache

def hydraulic_sow_create(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    next_url = request.GET.get('next')
    
    # Handle Export Requests (PDF, Word, Excel, CSV)
    export_format = request.GET.get('format')
    if export_format:
        # Placeholder for export logic
        # You would generate the file here based on 'export_format'
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="sow_{customer.pk}.{export_format}"'
        response.write(f"Exporting {export_format} for {customer.name}...")
        return response

    if request.method == 'POST':
        # Parse cost safely for logic
        cost_input = request.POST.get('cost')
        cost_decimal = Decimal('0.00')
        if cost_input:
            try:
                cost_decimal = Decimal(str(cost_input))
            except (ValueError, TypeError, InvalidOperation):
                pass

        sow = HydraulicSow.objects.create(
            customer=customer,
            created_by=request.user,
            hose_type=request.POST.get('hose_type', ''),
            diameter=request.POST.get('diameter', ''),
            length=request.POST.get('length') or None,
            pressure=request.POST.get('pressure') or None,
            application=request.POST.get('application', ''),
            fitting_a=request.POST.get('fitting_a', ''),
            fitting_b=request.POST.get('fitting_b', ''),
            orientation=request.POST.get('orientation') or None,
            protection=request.POST.get('protection', ''),
            cost=cost_decimal if cost_decimal > 0 else None,
            notes=request.POST.get('notes', '')
        )

        if cost_decimal > 0:
            payment_method = request.POST.get('payment_method', 'CREDIT')
            amount_paid = Decimal('0')
            
            if payment_method == 'CASH':
                amount_paid_input = request.POST.get('amount_paid')
                if amount_paid_input:
                    try:
                        amount_paid = Decimal(amount_paid_input)
                    except:
                        pass

            # Create Ledger Entry (POSSale)
            receipt_id = sow.sow_id
            POSSale.objects.create(
                receipt_id=receipt_id,
                customer=customer,
                cashier=request.user,
                payment_method=payment_method,
                total_amount=cost_decimal,
                amount_paid=amount_paid,
                change_given=(amount_paid - cost_decimal) if payment_method == 'CASH' else 0,
                notes=f"Hydraulic Job #{sow.id}: {sow.hose_type} ({sow.application})"
            )
            messages.success(request, f"Hydraulic SOW saved. Receipt generated.")
            return redirect('inventory:pos_receipt_detail', receipt_id=receipt_id)
        else:
            messages.success(request, f"Hydraulic Scope of Work saved for {customer.name}")
            
        if next_url:
            return redirect(next_url)
            
        return redirect('inventory:customer_detail', pk=pk)

    return render(request, 'inventory/hydraulic_sow_form.html', {
        'customer': customer,
        'page_title': 'Create Hydraulic SOW',
        'is_charged': False,
        'next_url': next_url,
    })

@login_required
def hydraulic_sow_update(request, pk, sow_pk):
    customer = get_object_or_404(Customer, pk=pk)
    sow = get_object_or_404(HydraulicSow, pk=sow_pk, customer=customer)
    
    # Ensure SOW ID exists (for legacy records)
    if not sow.sow_id:
        sow.save()

    if request.method == 'POST':
        # Update SOW fields
        sow.hose_type = request.POST.get('hose_type', '')
        sow.diameter = request.POST.get('diameter', '')
        sow.length = request.POST.get('length') or None
        sow.pressure = request.POST.get('pressure') or None
        sow.application = request.POST.get('application', '')
        sow.fitting_a = request.POST.get('fitting_a', '')
        sow.fitting_b = request.POST.get('fitting_b', '')
        sow.orientation = request.POST.get('orientation') or None
        sow.protection = request.POST.get('protection', '')
        sow.notes = request.POST.get('notes', '')

        cost_input = request.POST.get('cost')
        cost_decimal = Decimal('0.00')
        if cost_input:
            try:
                cost_decimal = Decimal(str(cost_input))
            except (ValueError, TypeError, InvalidOperation):
                pass
        sow.cost = cost_decimal if cost_decimal > 0 else None
        sow.save()

        # Handle charging logic
        charge_to_account = request.POST.get('charge_account')
        ledger_entry = POSSale.objects.filter(receipt_id=sow.sow_id).first()
        if not ledger_entry:
            ledger_entry = POSSale.objects.filter(receipt_id=f"SOW-{sow.id}").first()

        if ledger_entry:
            if ledger_entry.total_amount != cost_decimal:
                ledger_entry.total_amount = cost_decimal
                ledger_entry.save()
                messages.success(request, f"SOW updated. Associated charge was adjusted to ₱{cost_decimal:,.2f}.")
            else:
                messages.success(request, "SOW updated. No changes to the associated charge.")
        elif charge_to_account and cost_decimal > 0:
            POSSale.objects.create(receipt_id=sow.sow_id, customer=customer, cashier=request.user, payment_method='CREDIT', total_amount=cost_decimal, notes=f"Hydraulic Job #{sow.id}: {sow.hose_type} ({sow.application})")
            messages.success(request, f"SOW updated and a new charge of ₱{cost_decimal:,.2f} was added to the account.")
        else:
            messages.success(request, "Hydraulic SOW updated successfully.")
        return redirect('inventory:customer_detail', pk=pk)

    ledger_entry = POSSale.objects.filter(receipt_id=sow.sow_id).first()
    if not ledger_entry:
        ledger_entry = POSSale.objects.filter(receipt_id=f"SOW-{sow.id}").first()
    return render(request, 'inventory/hydraulic_sow_form.html', {'customer': customer, 'sow': sow, 'page_title': f'Edit Hydraulic SOW {sow.sow_id or sow.id}', 'is_charged': ledger_entry is not None})

def hydraulic_sow_import(request):
    if request.method == 'POST':
        # Handle file upload and parsing logic here
        messages.info(request, "Import functionality is under construction.")
        return redirect('inventory:customer_list')
        
    # You will need a simple template for this, or reuse a generic import template
    return render(request, 'inventory/form_import.html', {
        'title': 'Import Hydraulic SOW'
    })

@login_required
def export_sow_history(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    format_type = request.GET.get('format', 'pdf')
    sow_q = request.GET.get('sow_q', '')

    sows = customer.sows.select_related('created_by').all()
    
    if sow_q:
        q_sow = Q(sow_id__icontains=sow_q) | \
                Q(hose_type__icontains=sow_q) | \
                Q(application__icontains=sow_q) | \
                Q(notes__icontains=sow_q) | \
                Q(fitting_a__icontains=sow_q) | \
                Q(fitting_b__icontains=sow_q)
        if sow_q.isdigit():
            q_sow |= Q(id=sow_q)
        sows = sows.filter(q_sow)

    response = generate_sow_history_export(customer, sows, format_type, request)
    if response:
        return response
    return HttpResponse("Error Generating Export", status=500)

@login_required
def import_sow_history(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.xlsx')):
            messages.error(request, "Please upload a CSV or Excel file.")
            return redirect('inventory:customer_detail', pk=pk)

        try:
            data = []
            if csv_file.name.endswith('.csv'):
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                # Normalize headers
                reader.fieldnames = [name.strip().lower().replace(' ', '_') for name in reader.fieldnames]
                data = list(reader)
            elif csv_file.name.endswith('.xlsx'):
                wb = load_workbook(csv_file, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    headers = [str(h).strip().lower().replace(' ', '_') if h else '' for h in rows[0]]
                    for row in rows[1:]:
                        # Create dict, converting None to empty string to mimic CSV behavior
                        row_dict = {headers[i]: (str(val) if val is not None else '') for i, val in enumerate(row) if i < len(headers)}
                        data.append(row_dict)
            
            count = 0
            with transaction.atomic():
                for row in data:
                    cost_val = row.get('cost', 0)
                    if cost_val is None or cost_val == '': cost_val = 0
                    # Basic mapping, assuming CSV headers match model fields or close to it
                    HydraulicSow.objects.create(
                        customer=customer,
                        created_by=request.user,
                        hose_type=row.get('hose_type', ''),
                        diameter=row.get('diameter', ''),
                        length=row.get('length') or None,
                        pressure=row.get('pressure') or None,
                        cost=Decimal(str(cost_val)),
                        application=row.get('application', ''),
                        fitting_a=row.get('fitting_a', ''),
                        fitting_b=row.get('fitting_b', ''),
                        notes=row.get('notes', '')
                    )
                    count += 1
            messages.success(request, f"Imported {count} SOW records.")
        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            
        return redirect('inventory:customer_detail', pk=pk)

    return render(request, 'inventory/sow_import.html', {'customer': customer})


# --- EXPENSE MANAGEMENT ---

class ExpenseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Expense
    template_name = 'inventory/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    permission_required = 'inventory.view_expense'

    def get_queryset(self):
        queryset = Expense.objects.select_related('category', 'recorded_by').all()
        
        today = timezone.now().date()
        default_month = str(today.month)
        default_year = str(today.year)
        
        data = self.request.GET.copy()
        
        if not self.request.GET:
            data['month'] = default_month
            data['year'] = default_year
        
        self.filter_form = ExpenseFilterForm(data)
        if self.filter_form.is_valid():
            if self.filter_form.cleaned_data.get('q'):
                queryset = queryset.filter(description__icontains=self.filter_form.cleaned_data['q'])
            if self.filter_form.cleaned_data.get('category'):
                queryset = queryset.filter(category=self.filter_form.cleaned_data['category'])
            
            m = self.filter_form.cleaned_data.get('month')
            y = self.filter_form.cleaned_data.get('year')
            if y:
                queryset = queryset.filter(expense_date__year=y)
                if m:
                    queryset = queryset.filter(expense_date__month=m)
                
        return queryset.order_by('-expense_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['total_expenses'] = self.get_queryset().aggregate(total=Sum('amount'))['total'] or 0
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        
        if self.filter_form.is_valid():
            context['current_month'] = self.filter_form.cleaned_data.get('month')
            context['current_year'] = self.filter_form.cleaned_data.get('year')
            
            if context['current_year'] and not context['current_month']:
                context['period_name'] = f"Year {context['current_year']}"
            elif context['current_year'] and context['current_month']:
                try:
                    d = datetime(int(context['current_year']), int(context['current_month']), 1)
                    context['period_name'] = d.strftime('%B %Y')
                except:
                    context['period_name'] = "Selected Period"
            else:
                context['period_name'] = "All Time"
                
        return context

    def get(self, request, *args, **kwargs):
        export_format = request.GET.get('export')
        if export_format:
            return self.export_expenses(request, export_format)
        return super().get(request, *args, **kwargs)

    def export_expenses(self, request, format_type):
        expenses = self.get_queryset().order_by('expense_date')
        response = generate_expense_report(expenses, format_type, request)
        if response:
            return response
        messages.error(request, "Could not generate report. Invalid format specified.")
        return redirect('inventory:expense_list')

class ExpenseCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'inventory/expense_form.html'
    success_url = reverse_lazy('inventory:expense_list')
    success_message = "Expense recorded successfully."
    permission_required = 'inventory.add_expense'

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Record New Expense"
        return context
        
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['target_month'] = self.request.GET.get('month')
        kwargs['target_year'] = self.request.GET.get('year')
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        m = self.request.GET.get('month')
        y = self.request.GET.get('year')
        if y:
            try:
                today = timezone.now().date()
                if m:
                    target_date = datetime(int(y), int(m), 1).date()
                    if target_date.year == today.year and target_date.month == today.month:
                        initial['expense_date'] = today
                    else:
                        initial['expense_date'] = target_date
                else:
                    if str(today.year) == str(y):
                        initial['expense_date'] = today
                    else:
                        initial['expense_date'] = datetime(int(y), 1, 1).date()
            except:
                pass
        return initial

    def get_success_url(self):
        url = reverse_lazy('inventory:expense_list')
        m = self.request.GET.get('month')
        y = self.request.GET.get('year')
        
        params = []
        if m: params.append(f"month={m}")
        if y: params.append(f"year={y}")
        
        if params:
            return f"{url}?{'&'.join(params)}"
        return url

class ExpenseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'inventory/expense_form.html'
    success_url = reverse_lazy('inventory:expense_list')
    success_message = "Expense updated successfully."
    permission_required = 'inventory.change_expense'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Edit Expense"
        return context

class ExpenseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, DeleteView):
    model = Expense
    template_name = 'inventory/expense_confirm_delete.html'
    success_url = reverse_lazy('inventory:expense_list')
    success_message = "Expense deleted successfully."
    permission_required = 'inventory.delete_expense'

    def test_func(self):
        expense = self.get_object()
        return self.request.user == expense.recorded_by or self.request.user.is_superuser

@login_required
@permission_required('inventory.add_expense', raise_exception=True)
def import_expenses(request):
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.xlsx')):
            messages.error(request, "Please upload a CSV or Excel file.")
            return redirect('inventory:expense_list')

        try:
            data = []
            if csv_file.name.endswith('.csv'):
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                reader.fieldnames = [name.strip().lower().replace(' ', '_') for name in reader.fieldnames]
                data = list(reader)
            elif csv_file.name.endswith('.xlsx'):
                wb = load_workbook(csv_file, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    headers = [str(h).strip().lower().replace(' ', '_') if h else '' for h in rows[0]]
                    for row in rows[1:]:
                        # Keep native types for date/amount if possible, but handle None
                        row_dict = {headers[i]: val for i, val in enumerate(row) if i < len(headers)}
                        data.append(row_dict)
            
            count = 0
            with transaction.atomic():
                for row in data:
                    cat_name = row.get('category')
                    category = None
                    if cat_name:
                        category, _ = ExpenseCategory.objects.get_or_create(name=cat_name.strip())

                    # Handle Date (Excel returns datetime, CSV returns string)
                    date_val = row.get('date')
                    if hasattr(date_val, 'date'): # datetime object
                        date_val = date_val.date()
                    
                    # Handle Amount (Excel returns int/float, CSV returns string)
                    amount_val = row.get('amount', 0)
                    if amount_val is None: amount_val = 0

                    Expense.objects.create(
                        expense_date=date_val,
                        category=category,
                        description=row.get('description', ''),
                        amount=Decimal(str(amount_val)),
                        recorded_by=request.user
                    )
                    count += 1
            messages.success(request, f"Successfully imported {count} expenses.")
        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            
        return redirect('inventory:expense_list')
        
    return render(request, 'inventory/expense_import.html')

# DRF & Swagger Imports
from rest_framework import viewsets, permissions, filters
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .serializers import ProductSerializer, CategorySerializer

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
        qs = Customer.objects.exclude(name="Walk-in Customer").order_by('name')
        self.filter_form = CustomerFilterForm(self.request.GET)
        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get('q')
            if q:
                qs = qs.filter(
                    Q(name__icontains=q) | 
                    Q(email__icontains=q) | 
                    Q(phone__icontains=q) | 
                    Q(address__icontains=q)
                )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

    def get(self, request, *args, **kwargs):
        export_format = request.GET.get('export')
        if export_format:
            return self.export_customers(export_format)
        return super().get(request, *args, **kwargs)

    def export_customers(self, format_type):
        customers = self.get_queryset()
        response = generate_customer_list_export(customers, format_type, self.request)
        if response:
            return response
        messages.error(self.request, "Error generating export.")
        return redirect('inventory:customer_list')

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
        
        # Ensure legacy customers have a unique ID generated
        if not customer.customer_id:
            customer.save()
        
        ledger_q = self.request.GET.get('ledger_q', '')

        # 1. Fetch Sales (Credit) with payment status
        sales_qs = customer.purchases.all().select_related('cashier').annotate(
            paid_amount=Coalesce(Sum('payments_received__amount'), Decimal('0.00'))
        ).annotate(
            outstanding=F('total_amount') - F('paid_amount')
        )
        
        # 2. Fetch Payments
        payments_qs = customer.payments.select_related('recorded_by', 'sale_paid')

        if ledger_q:
            query_lower = ledger_q.lower()
            q_sales = Q(receipt_id__icontains=ledger_q) | Q(notes__icontains=ledger_q)
            q_payments = Q(reference_number__icontains=ledger_q) | Q(notes__icontains=ledger_q)

            # Amount Search
            try:
                amount_val = Decimal(ledger_q.replace(',', ''))
                q_sales |= Q(total_amount=amount_val)
                q_payments |= Q(amount=amount_val)
            except (ValueError, TypeError, InvalidOperation):
                pass

            # Keyword Search (Type/Description)
            if 'debt' in query_lower:
                q_sales = Q(payment_method='CREDIT', outstanding__gt=0)
                q_payments = Q(pk__in=[])
            elif 'sale' in query_lower:
                q_sales = Q(payment_method='CASH') | Q(payment_method='CREDIT', outstanding__lte=0)
                q_payments = Q(pk__in=[])
            elif 'payment' in query_lower:
                q_sales = Q(pk__in=[])
                q_payments = Q()
            elif any(k in query_lower for k in ['credit', 'purchase']):
                q_sales = Q()
                # q_payments remains based on text search

            sales_qs = sales_qs.filter(q_sales)
            payments_qs = payments_qs.filter(q_payments)

        payments = list(payments_qs.annotate(
            txn_type=Value('PAYMENT', output_field=models.CharField())
        ).values('payment_date', 'reference_number', 'amount', 'txn_type', 'sale_paid__receipt_id', 'recorded_by__username', 'notes'))
        
        # 3. Combine and Normalize
        ledger = []
        for s in sales_qs:
            status = "PAID"
            txn_type = 'SALE'
            credit_val = Decimal('0')

            if s.payment_method == 'CREDIT':
                if s.outstanding <= Decimal('0.001'):
                    status = "PAID"
                    txn_type = 'SALE' # Paid off debt becomes Sale
                elif s.paid_amount > 0:
                    status = "PARTIALLY PAID"
                    txn_type = 'DEBT'
                else:
                    status = "UNPAID"
                    txn_type = 'DEBT'
            else:
                # Cash/Card Sales are effectively paid immediately and are Sales
                status = "PAID"
                txn_type = 'SALE'
                credit_val = s.total_amount # Offset debit so balance doesn't increase

            ledger.append({
                'date': s.timestamp,
                'ref': s.receipt_id,
                'description': f'{s.get_payment_method_display()} ({status})',
                'debit': s.total_amount,
                'credit': credit_val,
                'type': txn_type,
                'view_url': reverse('inventory:pos_receipt_detail', kwargs={'receipt_id': s.receipt_id}),
                'user': s.cashier.username if s.cashier else 'N/A'
            })
        for p in payments:
            desc = 'Payment Received'
            view_url = None
            if p['sale_paid__receipt_id']:
                desc += f" (for {p['sale_paid__receipt_id']})"
                view_url = reverse('inventory:pos_receipt_detail', kwargs={'receipt_id': p['sale_paid__receipt_id']})
            if p['notes']:
                desc += f" - {p['notes']}"
            ledger.append({
                'date': p['payment_date'],
                'ref': p['reference_number'],
                'description': desc,
                'debit': 0,
                'credit': p['amount'],
                'type': 'PAYMENT',
                'view_url': view_url,
                'user': p.get('recorded_by__username') or 'N/A'
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
        context['payment_form'] = CustomerPaymentForm(customer=customer)
        current_balance = self.object.get_balance()
        credit_limit = self.object.credit_limit
        context['current_balance'] = current_balance
        context['available_credit'] = credit_limit - current_balance
        
        # SOW Filtering
        sow_q = self.request.GET.get('sow_q', '')
        sows_qs = self.object.sows.select_related('created_by').all()

        if sow_q:
            q_sow = Q(sow_id__icontains=sow_q) | \
                    Q(hose_type__icontains=sow_q) | \
                    Q(application__icontains=sow_q) | \
                    Q(notes__icontains=sow_q) | \
                    Q(fitting_a__icontains=sow_q) | \
                    Q(fitting_b__icontains=sow_q)
            if sow_q.isdigit():
                q_sow |= Q(id=sow_q)
            sows_qs = sows_qs.filter(q_sow)

        context['sows'] = sows_qs
        context['sow_q'] = sow_q
        
        context['ledger_q'] = ledger_q
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()

        return context

@login_required
@require_POST
def customer_payment(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerPaymentForm(request.POST, customer=customer)
    if form.is_valid():
        payment = form.save(commit=False)

        sale_paid = form.cleaned_data.get('sale_paid')
        amount = form.cleaned_data.get('amount')

        if sale_paid:
            # Check for overpayment on a specific invoice
            paid_so_far = sale_paid.payments_received.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            outstanding = sale_paid.total_amount - paid_so_far
            
            if amount > outstanding + Decimal('0.001'): # Add tolerance
                messages.error(request, f"Payment of {amount:,.2f} exceeds the outstanding amount of {outstanding:,.2f} for invoice {sale_paid.receipt_id}.")
                return redirect('inventory:customer_detail', pk=pk)
        else:
            # General payment: Check against total customer balance
            current_balance = customer.get_balance()
            if amount > current_balance + Decimal('0.001'):
                messages.error(request, f"Payment of {amount:,.2f} exceeds the total outstanding balance of {current_balance:,.2f}.")
                return redirect('inventory:customer_detail', pk=pk)

        payment.customer = customer
        payment.recorded_by = request.user
        payment.save()
        messages.success(request, "Payment recorded successfully.")
    else:
        error_str = " ".join([f"{field.replace('_', ' ').title()}: {error}" for field, err_list in form.errors.items() for error in err_list])
        messages.error(request, f"Error recording payment. {error_str if error_str else 'Please check your input.'}")
    return redirect('inventory:customer_detail', pk=pk)

@login_required
def import_customers(request):
    """Simple CSV Import for Customers"""
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.xlsx')):
            messages.error(request, "Please upload a CSV or Excel file.")
            return redirect('inventory:customer_list')

        try:
            data = []
            if csv_file.name.endswith('.csv'):
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                data = list(reader)
            elif csv_file.name.endswith('.xlsx'):
                wb = load_workbook(csv_file, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    headers = [str(h).strip().lower() if h else '' for h in rows[0]]
                    for row in rows[1:]:
                        row_dict = {headers[i]: (str(val) if val is not None else '') for i, val in enumerate(row) if i < len(headers)}
                        data.append(row_dict)

            count = 0
            for row in data:
                # Expects columns: name, email, phone, address
                if row.get('name'):
                    Customer.objects.update_or_create(
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
        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.xlsx')):
            messages.error(request, "Please upload a CSV or Excel file.")
            return redirect('inventory:customer_detail', pk=pk)

        try:
            data = []
            if csv_file.name.endswith('.csv'):
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
                data = list(reader)
            elif csv_file.name.endswith('.xlsx'):
                wb = load_workbook(csv_file, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    headers = [str(h).strip().lower() if h else '' for h in rows[0]]
                    for row in rows[1:]:
                        # Keep native types for date/numbers
                        row_dict = {headers[i]: val for i, val in enumerate(row) if i < len(headers)}
                        data.append(row_dict)
            
            # Expected headers mapping (naive)
            # We expect: date, reference, description, charge, payment
            
            count_charges = 0
            count_payments = 0
            
            with transaction.atomic():
                for row in data:
                    # Parse Date
                    date_val = row.get('date')
                    try:
                        if isinstance(date_val, (datetime, datetime.date)):
                            txn_date = date_val
                            if not timezone.is_aware(txn_date) and isinstance(txn_date, datetime):
                                txn_date = timezone.make_aware(txn_date)
                        else:
                            txn_date = datetime.strptime(str(date_val), '%Y-%m-%d')
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
    
    ledger_q = request.GET.get('ledger_q', '')

    # --- DATA PREPARATION (aligned with CustomerDetailView) ---
    # 1. Fetch Sales (Credit) with payment status
    sales_qs = customer.purchases.all().select_related('cashier').annotate(
        paid_amount=Coalesce(Sum('payments_received__amount'), Decimal('0.00'))
    ).annotate(
        outstanding=F('total_amount') - F('paid_amount')
    )
    
    # 2. Fetch Payments
    payments_qs = customer.payments.select_related('recorded_by', 'sale_paid')

    if ledger_q:
        query_lower = ledger_q.lower()
        q_sales = Q(receipt_id__icontains=ledger_q) | Q(notes__icontains=ledger_q)
        q_payments = Q(reference_number__icontains=ledger_q) | Q(notes__icontains=ledger_q)

        # Amount Search
        try:
            amount_val = Decimal(ledger_q.replace(',', ''))
            q_sales |= Q(total_amount=amount_val)
            q_payments |= Q(amount=amount_val)
        except (ValueError, TypeError, InvalidOperation):
            pass

        # Keyword Search (Type/Description)
        if 'debt' in query_lower:
            q_sales = Q(payment_method='CREDIT', outstanding__gt=0)
            q_payments = Q(pk__in=[])
        elif 'sale' in query_lower:
            q_sales = Q(payment_method='CASH') | Q(payment_method='CREDIT', outstanding__lte=0)
            q_payments = Q(pk__in=[])
        elif 'payment' in query_lower:
            q_sales = Q(pk__in=[])
            q_payments = Q()
        elif any(k in query_lower for k in ['credit', 'purchase']):
            q_sales = Q()
            # q_payments remains based on text search

        sales_qs = sales_qs.filter(q_sales)
        payments_qs = payments_qs.filter(q_payments)

    payments = list(payments_qs.annotate(
        txn_type=Value('PAYMENT', output_field=models.CharField())
    ).values('payment_date', 'reference_number', 'amount', 'txn_type', 'sale_paid__receipt_id', 'recorded_by__username', 'notes'))
    
    # 3. Combine and Normalize
    ledger = []
    for s in sales_qs:
        status = "PAID"
        credit_val = Decimal('0')

        if s.payment_method == 'CREDIT':
            if s.outstanding <= Decimal('0.001'):
                status = "PAID"
            elif s.paid_amount > 0:
                status = "PARTIALLY PAID"
            else:
                status = "UNPAID"
        else:
            # Cash/Card
            status = "PAID"
            credit_val = s.total_amount

        ledger.append({
            'date': s.timestamp,
            'ref': s.receipt_id,
            'description': f'{s.get_payment_method_display()} ({status})',
            'debit': s.total_amount,
            'credit': credit_val,
            'user': s.cashier.username if s.cashier else 'N/A'
        })
    for p in payments:
        desc = 'Payment Received'
        if p['sale_paid__receipt_id']:
            desc += f" (for {p['sale_paid__receipt_id']})"
        if p['notes']:
            desc += f" - {p['notes']}"
        ledger.append({
            'date': p['payment_date'],
            'ref': p['reference_number'],
            'description': desc,
            'debit': Decimal('0'),
            'credit': p['amount'],
            'user': p.get('recorded_by__username') or 'N/A'
        })
        
    # 4. Sort by date
    ledger.sort(key=lambda x: x['date'])

    # 5. Calculate Running Balance
    balance = Decimal('0')
    for entry in ledger:
        balance += (entry['debit'] - entry['credit'])
        entry['balance'] = balance

    response = generate_customer_statement(customer, ledger, balance, format_type, request)
    if response:
        return response
    return HttpResponse("Error Generating Export", status=500)

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
            
            stock_status = form.cleaned_data.get('stock_status')
            if stock_status:
                if stock_status == 'in_stock':
                    queryset = queryset.filter(quantity__gt=10)
                elif stock_status == 'low_stock':
                    queryset = queryset.filter(quantity__gt=0, quantity__lte=10)
                elif stock_status == 'out_of_stock':
                    queryset = queryset.filter(quantity=0)

            sort_by = form.cleaned_data.get('sort_by')
            if sort_by:
                queryset = queryset.order_by(sort_by)
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
        context['refund_form'] = RefundForm(product=self.object)
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
    form = RefundForm(request.POST, product=product)
    
    if form.is_valid():
        sale = form.cleaned_data['pos_sale']
        receipt_id = sale.receipt_id
        quantity = form.cleaned_data['quantity']
        notes = form.cleaned_data.get('notes')

        # 2. Verify Product was in that Receipt
        sold_items = StockTransaction.objects.filter(
            pos_sale=sale,
            product=product,
            transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE
        )
        total_sold = sold_items.aggregate(total=Sum('quantity'))['total'] or 0

        if total_sold == 0:
            messages.error(request, f"Product '{product.name}' was not found in Receipt {receipt_id}.")
            return redirect(product.get_absolute_url())

        # 3. Check Previous Returns (Prevent over-refunding)
        returned_items = StockTransaction.objects.filter(
            pos_sale=sale,
            product=product,
            transaction_type='IN',
            transaction_reason=StockTransaction.TransactionReason.RETURN
        )
        total_returned = returned_items.aggregate(total=Sum('quantity'))['total'] or 0

        if (total_returned + quantity) > total_sold:
            remaining = total_sold - total_returned
            messages.error(request, f"Cannot refund {quantity}. Only {remaining} items eligible for return from this receipt.")
            return redirect(product.get_absolute_url())

        with transaction.atomic():
            StockTransaction.objects.create(
                product=product,
                transaction_type='IN',
                transaction_reason=StockTransaction.TransactionReason.RETURN,
                quantity=quantity,
                user=request.user,
                selling_price=product.price, 
                pos_sale=sale,
                notes=f"Refund for Receipt {receipt_id}: {notes}"
            )
            product.quantity += quantity
            product.save()
            messages.success(request, f"Refund processed. {quantity} items returned from Receipt {receipt_id}.")
    else:
        for field, errors in form.errors.items():
            messages.error(request, f"{field}: {', '.join(errors)}")
            
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

def get_walkin_customer():
    """Helper to get or create the default Walk-in Customer."""
    customer, created = Customer.objects.get_or_create(
        name="Walk-in Customer",
        defaults={
            'email': '',
            'phone': '',
            'address': 'Store Counter',
            'tax_id': '',
            'credit_limit': 0
        }
    )
    return customer

@login_required
@permission_required('inventory.can_adjust_stock', raise_exception=True)
def pos_dashboard(request):
    # Products
    active_products_qs = Product.objects.filter(status=Product.Status.ACTIVE, quantity__gt=0).values(
        'id', 'name', 'sku', 'price', 'quantity', 'category__name', 'image'
    )

    # Manually process to add the full image URL
    products_list = []
    for p in active_products_qs:
        image_url = None
        if p.get('image'):
            # Construct the full URL path for the template
            image_url = f"{settings.MEDIA_URL}{p['image']}"
        p['image_url'] = image_url
        products_list.append(p)

    products_json = json.dumps(products_list, cls=DjangoJSONEncoder)
    
    # Customers
    customers = Customer.objects.values('id', 'name', 'credit_limit')
    customers_json = json.dumps(list(customers), cls=DjangoJSONEncoder)
    
    # Get pre-selected customer from URL
    preselected_customer_id = request.GET.get('customer_id')

    # Ensure Walk-in Customer exists
    walkin_customer = get_walkin_customer()

    context = {
        'page_title': 'Point of Sale',
        'products_json': products_json,
        'customers_json': customers_json,
        'preselected_customer_id': preselected_customer_id,
        'walkin_customer': walkin_customer,
    }
    return render(request, 'inventory/pos.html', context)

@login_required
def pos_sow_create(request):
    walkin = get_walkin_customer()
    # Redirect to SOW create with next=pos_dashboard
    url = reverse('inventory:hydraulic_sow_create', kwargs={'pk': walkin.pk})
    next_url = reverse('inventory:pos_dashboard')
    return redirect(f"{url}?next={next_url}")

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
        qs = POSSale.objects.select_related('cashier', 'customer').order_by('-timestamp')
        q = self.request.GET.get('q')
        if q:
            query = Q(receipt_id__icontains=q) | \
                    Q(customer__name__icontains=q) | \
                    Q(cashier__username__icontains=q)
            try:
                amount_val = Decimal(q.replace(',', ''))
                query |= Q(total_amount=amount_val)
            except (ValueError, TypeError, InvalidOperation):
                pass
            qs = qs.filter(query)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        
        return context

class POSReceiptDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = POSSale
    template_name = 'inventory/pos_receipt.html'
    context_object_name = 'sale'
    permission_required = 'inventory.view_stocktransaction'
    
    def get_object(self):
        return get_object_or_404(POSSale, receipt_id=self.kwargs['receipt_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product').annotate(
            line_total=ExpressionWrapper(F('quantity') * F('selling_price'), output_field=DecimalField())
        )
        return context

# --- ANALYTICS & REPORTS ---

@method_decorator(xframe_options_exempt, name='dispatch')
class ReportingView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'inventory/reporting.html'
    permission_required = 'inventory.can_view_reports'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Report Generation"
        context['transaction_report_form'] = TransactionReportForm(self.request.GET or None)
        return context

    def get(self, request, *args, **kwargs):
        export_type = request.GET.get('export')
        if export_type == 'inventory_csv': return self.export_inventory_csv()
        elif export_type == 'transaction_pdf': return self.export_transactions_pdf(request)
        return super().get(request, *args, **kwargs)

    def export_inventory_csv(self):
        products = Product.objects.select_related('category').all()
        return generate_inventory_csv(products)

    def export_transactions_pdf(self, request):
        form = TransactionReportForm(request.GET)
        
        start_date, end_date = None, None
        transactions = StockTransaction.objects.select_related('product', 'user').all()

        if form.is_valid():
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            if start_date:
                start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
                transactions = transactions.filter(timestamp__gte=start_dt)
            if end_date:
                end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
                transactions = transactions.filter(timestamp__lte=end_dt)
        
        transactions = transactions.annotate(
            row_total=ExpressionWrapper(F('quantity') * F('selling_price'), output_field=DecimalField())
        ).order_by('-timestamp')

        sales_txns = transactions.filter(transaction_reason=StockTransaction.TransactionReason.SALE)
        refund_txns = transactions.filter(transaction_reason=StockTransaction.TransactionReason.RETURN)

        gross_sales = sales_txns.aggregate(total=Sum('row_total'))['total'] or Decimal('0.00')
        total_refunds = refund_txns.aggregate(total=Sum('row_total'))['total'] or Decimal('0.00')
        net_revenue = gross_sales - total_refunds
        total_items_sold = sales_txns.aggregate(total=Sum('quantity'))['total'] or 0

        inflow_summary = transactions.filter(transaction_type='IN').values('transaction_reason').annotate(total_qty=Sum('quantity')).order_by('-total_qty')
        
        loss_summary = transactions.filter(
            transaction_reason__in=[StockTransaction.TransactionReason.DAMAGE, StockTransaction.TransactionReason.INTERNAL]
        ).annotate(
            lost_value=ExpressionWrapper(F('quantity') * F('product__price'), output_field=DecimalField())
        ).values('transaction_reason').annotate(
            total_qty=Sum('quantity'), total_val=Sum('lost_value')
        ).order_by('-total_val')

        top_sellers = sales_txns.values('product__name').annotate(
            total_quantity_sold=Sum('quantity')
        ).order_by('-total_quantity_sold')[:5]

        context = {
            'transactions': transactions, 'start_date': start_date, 'end_date': end_date,
            'gross_sales': gross_sales, 'total_refunds': total_refunds, 'net_revenue': net_revenue,
            'total_items_sold': total_items_sold, 'inflow_summary': inflow_summary,
            'loss_summary': loss_summary, 'top_sellers': top_sellers, 'today': timezone.now(),
        }

        pdf = render_to_pdf('inventory/transaction_report_pdf.html', context, request=request)
        
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            filename = f"Stock_Movement_Report_{timezone.now().strftime('%Y%m%d')}.pdf"
            if 'preview' in request.GET:
                response['Content-Disposition'] = f'inline; filename="{filename}"'
            else:
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        messages.error(request, "Could not generate PDF report. Please try again.")
        return redirect('inventory:reporting')

@login_required
def analytics_dashboard(request):
    # 1. Date Filtering
    today = timezone.now().date()
    
    # Default to current month/year
    default_month = str(today.month)
    default_year = str(today.year)
    
    data = request.GET.copy()
    if not request.GET:
        data['month'] = default_month
        data['year'] = default_year
    
    filter_form = AnalyticsFilterForm(data)
    
    # Determine Date Range & Period Name
    start_date = today.replace(day=1)
    end_date = today
    period_name = start_date.strftime('%B %Y')

    if filter_form.is_valid():
        m = filter_form.cleaned_data.get('month')
        y = filter_form.cleaned_data.get('year')
        
        if y:
            year_val = int(y)
            if m:
                month_val = int(m)
                start_date = datetime(year_val, month_val, 1).date()
                # Calculate last day of month
                if month_val == 12:
                    end_date = datetime(year_val + 1, 1, 1).date() - timedelta(days=1)
                else:
                    end_date = datetime(year_val, month_val + 1, 1).date() - timedelta(days=1)
                period_name = start_date.strftime('%B %Y')
            else:
                # Full Year
                start_date = datetime(year_val, 1, 1).date()
                end_date = datetime(year_val, 12, 31).date()
                period_name = f"Year {y}"

    # Make end_date inclusive (end of the day)
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    # 2. Base Querysets
    pos_sales = POSSale.objects.filter(timestamp__range=[start_dt, end_dt])
    stock_txns = StockTransaction.objects.filter(timestamp__range=[start_dt, end_dt])
    expenses_qs = Expense.objects.filter(expense_date__range=[start_date, end_date])
    
    # 3. KPI Calculations
    # Optimized: Use conditional aggregation to reduce DB queries
    stock_metrics = stock_txns.aggregate(
        refunds_val=Sum(
            F('quantity') * F('selling_price'),
            filter=Q(transaction_type='IN', transaction_reason=StockTransaction.TransactionReason.RETURN)
        ),
        units_sold=Sum(
            'quantity',
            filter=Q(transaction_type='OUT', transaction_reason=StockTransaction.TransactionReason.SALE)
        ),
        loss_val=Sum(
            F('quantity') * F('product__price'),
            filter=Q(transaction_reason=StockTransaction.TransactionReason.DAMAGE)
        ),
        refunds_count=Count(
            'id',
            filter=Q(transaction_type='IN', transaction_reason=StockTransaction.TransactionReason.RETURN)
        ),
        damages_count=Count(
            'id',
            filter=Q(transaction_reason=StockTransaction.TransactionReason.DAMAGE)
        )
    )
    
    gross_sales_val = pos_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_refunds_val = stock_metrics['refunds_val'] or Decimal('0.00')
    total_units = stock_metrics['units_sold'] or 0
    total_loss = stock_metrics['loss_val'] or Decimal('0.00')
    
    total_refunds_count = stock_metrics['refunds_count'] or 0
    total_damages_count = stock_metrics['damages_count'] or 0
    
    charges_qs = pos_sales.filter(payment_method='CREDIT')
    charges_count = charges_qs.count()
    total_charges_val = charges_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    # Correct Financial Logic
    # Gross Sales = Total money from sales (before refunds)
    # Net Revenue = Gross Sales - Refunds
    # Net Income  = Net Revenue - Expenses
    
    net_revenue_val = gross_sales_val - total_refunds_val
    net_income = net_revenue_val - total_expenses
    

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
    
    # C. Expenses by Category
    exp_cat_qs = expenses_qs.values('category__name').annotate(total=Sum('amount')).order_by('-total')
    exp_cat_labels = [item['category__name'] or 'Uncategorized' for item in exp_cat_qs]
    exp_cat_values = [float(item['total']) for item in exp_cat_qs]
    
    # D. Financial Trend (Sales vs Expenses)
    sales_trend = pos_sales.annotate(date=TruncDate('timestamp')).values('date').annotate(daily_total=Sum('total_amount')).order_by('date')
    sales_map = {item['date']: item['daily_total'] for item in sales_trend}

    exp_trend = expenses_qs.values('expense_date').annotate(daily_total=Sum('amount')).order_by('expense_date')
    exp_map = {item['expense_date']: item['daily_total'] for item in exp_trend}

    all_dates = sorted(list(set(list(sales_map.keys()) + list(exp_map.keys()))))
    
    trend_labels = [d.strftime('%b %d') for d in all_dates]
    trend_sales_values = [float(sales_map.get(d, 0)) for d in all_dates]
    trend_expense_values = [float(exp_map.get(d, 0)) for d in all_dates]
    
    # E. Sales vs Charges (Payment Method)
    pay_qs = pos_sales.values('payment_method').annotate(total=Sum('total_amount')).order_by('-total')
    pay_labels = []
    pay_values = []
    for item in pay_qs:
        method = item['payment_method']
        if method == 'CREDIT':
            pay_labels.append('Charges (Credit)')
        elif method == 'CASH':
            pay_labels.append('Cash Sales')
        elif method == 'CARD':
            pay_labels.append('Card Sales')
        else:
            pay_labels.append(method)
        pay_values.append(float(item['total']))

    context = {
        'filter_form': filter_form,
        'start_date': start_date,
        'end_date': end_date,
        'period_name': period_name,
        
        # KPIs
        'total_revenue': net_revenue_val, # Template label is "Net Revenue"
        'gross_sales': gross_sales_val,   # Template label is "Gross"
        'total_expenses': total_expenses,
        'net_income': net_income,
        'total_units': total_units,
        'total_refunds': total_refunds_val,
        'total_loss': total_loss,
        'charges_count': charges_count,
        'total_charges_val': total_charges_val,
        'refunds_count': total_refunds_count,
        'damages_count': total_damages_count,
        
        # Charts (JSON)
        'cat_labels': json.dumps(cat_labels),
        'cat_values': json.dumps(cat_values),
        'exp_cat_labels': json.dumps(exp_cat_labels),
        'exp_cat_values': json.dumps(exp_cat_values),
        'prod_labels': json.dumps(prod_labels),
        'prod_values': json.dumps(prod_values),
        'trend_labels': json.dumps(trend_labels),
        'trend_sales_values': json.dumps(trend_sales_values),
        'trend_expense_values': json.dumps(trend_expense_values),
        'pay_labels': json.dumps(pay_labels),
        'pay_values': json.dumps(pay_values),
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
        queryset = PurchaseOrder.objects.select_related('supplier').order_by('-order_date')
        self.filter_form = PurchaseOrderFilterForm(self.request.GET)
        if self.filter_form.is_valid():
            if self.filter_form.cleaned_data.get('supplier'):
                queryset = queryset.filter(supplier=self.filter_form.cleaned_data['supplier'])
            if self.filter_form.cleaned_data.get('status'):
                queryset = queryset.filter(status=self.filter_form.cleaned_data['status'])
            if self.filter_form.cleaned_data.get('start_date'):
                queryset = queryset.filter(order_date__date__gte=self.filter_form.cleaned_data['start_date'])
            if self.filter_form.cleaned_data.get('end_date'):
                queryset = queryset.filter(order_date__date__lte=self.filter_form.cleaned_data['end_date'])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

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
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().order_by('name')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(contact_person__icontains=q) |
                Q(email__icontains=q) |
                Q(supplier_id__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context

class SupplierDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Supplier
    template_name = 'inventory/supplier_detail.html'
    context_object_name = 'supplier'
    permission_required = 'inventory.view_supplier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        po_list = supplier.purchase_orders.all().order_by('-order_date')
        
        paginator = Paginator(po_list, 15)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['purchase_orders'] = page_obj
        context['is_paginated'] = page_obj.has_other_pages()
        context['page_obj'] = page_obj
        
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        export_format = request.GET.get('export')
        if export_format:
            return self.export_deliveries(export_format)
        
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_purchase_orders(self):
        return self.object.purchase_orders.prefetch_related('items', 'items__product').order_by('-order_date')

    def export_deliveries(self, format_type):
        supplier = self.object
        purchase_orders = self.get_purchase_orders()
        response = generate_supplier_deliveries_export(supplier, purchase_orders, format_type, self.request)
        if response:
            return response
        messages.error(self.request, "Error generating export.")
        return redirect('inventory:supplier_detail', pk=supplier.pk)

@login_required
@permission_required('inventory.add_purchaseorder', raise_exception=True)
def import_supplier_deliveries(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST" and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.xlsx')):
            messages.error(request, "Please upload a CSV or Excel file.")
            return redirect('inventory:supplier_detail', pk=pk)
        try:
            data = []
            if csv_file.name.endswith('.csv'):
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                reader.fieldnames = [name.strip().lower().replace(' ', '_') for name in reader.fieldnames]
                data = list(reader)
            elif csv_file.name.endswith('.xlsx'):
                wb = load_workbook(csv_file, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    headers = [str(h).strip().lower().replace(' ', '_') if h else '' for h in rows[0]]
                    for row in rows[1:]:
                        row_dict = {headers[i]: val for i, val in enumerate(row) if i < len(headers)}
                        data.append(row_dict)

            created_pos = {}
            items_added = 0
            with transaction.atomic():
                for row in data:
                    po_id = row.get('po_id')
                    product_sku = row.get('product_sku')
                    
                    # Handle Excel int/float vs CSV string
                    qty_val = row.get('quantity', 0)
                    if qty_val is None: qty_val = 0
                    quantity = int(qty_val)
                    
                    price_val = row.get('price', 0)
                    if price_val is None: price_val = 0
                    price = Decimal(str(price_val))

                    if not all([po_id, product_sku, quantity > 0]):
                        continue
                    if po_id not in created_pos:
                        po, created = PurchaseOrder.objects.get_or_create(order_id=po_id, defaults={'supplier': supplier, 'status': 'PENDING'})
                        if not created and po.supplier != supplier:
                            raise ValueError(f"Purchase Order ID {po_id} already exists for another supplier.")
                        created_pos[po_id] = po
                    po = created_pos[po_id]
                    try:
                        product = Product.objects.get(sku=product_sku)
                    except Product.DoesNotExist:
                        messages.warning(request, f"Product with SKU '{product_sku}' not found. Skipping item in PO {po_id}.")
                        continue
                    PurchaseOrderItem.objects.create(purchase_order=po, product=product, quantity=quantity, price=price)
                    items_added += 1
            messages.success(request, f"Successfully imported {items_added} items across {len(created_pos)} Purchase Orders.")
        except ValueError as e:
            messages.error(request, f"Data error: {e}")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
        return redirect('inventory:supplier_detail', pk=pk)
    return render(request, 'inventory/supplier_deliveries_import.html', {'supplier': supplier})

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
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'sku']

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
@require_POST
def add_expense_category_ajax(request):
    name = request.POST.get('name')
    if name:
        cat, created = ExpenseCategory.objects.get_or_create(name=name)
        return JsonResponse({'status': 'success', 'category': {'id': cat.id, 'name': cat.name}})
    return JsonResponse({'status': 'error', 'message': 'Category name is required.'}, status=400)

@login_required
def search_products(request):
    """AJAX endpoint for searching products by name or SKU."""
    query = request.GET.get('q', '')
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(sku__icontains=query)
        ).filter(status=Product.Status.ACTIVE).values('id', 'name', 'sku', 'price', 'quantity')[:20]
        return JsonResponse({'results': list(products)})
    return JsonResponse({'results': []})

@login_required
def sales_chart_data(request):
    # Removed Hour and Minute sales as requested, defaulting to daily view
    now = timezone.now()
    start_time = now - timedelta(days=30)
    trunc_func = TruncDate('timestamp')
    date_format = '%b %d'

    # Fetch POS Sales grouped by Date and Payment Method
    sales_qs = POSSale.objects.filter(timestamp__gte=start_time).annotate(
        period_group=trunc_func
    ).values('period_group', 'payment_method').annotate(
        total=Sum('total_amount')
    ).order_by('period_group')
    
    # Organize data into dictionaries
    sales_by_date = {}
    charges_by_date = {}

    for entry in sales_qs:
        d = entry['period_group']
        if isinstance(d, datetime): d = d.date()
        
        amount = float(entry['total'])
        if entry['payment_method'] == 'CREDIT':
            charges_by_date[d] = charges_by_date.get(d, 0) + amount
        else:
            # Group CASH and CARD as "Sales" (Revenue realized immediately)
            sales_by_date[d] = sales_by_date.get(d, 0) + amount

    # Generate continuous date range
    labels = []
    sales_data = []
    charges_data = []
    
    current_date = start_time.date()
    end_date = now.date()
    
    while current_date <= end_date:
        labels.append(current_date.strftime(date_format))
        sales_data.append(sales_by_date.get(current_date, 0))
        charges_data.append(charges_by_date.get(current_date, 0))
        current_date += timedelta(days=1)
    
    return JsonResponse({
        'labels': labels, 
        'sales_data': sales_data,
        'charges_data': charges_data
    })

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

def process_history_records(history_records):
    """Helper to calculate deltas and action labels for history records."""
    for record in history_records:
        record.change_summary_html = "No details available."
        record.action_label = "Update"
        record.badge_class = "bg-secondary-subtle text-secondary border border-secondary"

        if record.history_type == '+':
            record.action_label = "Created"
            record.badge_class = "bg-success-subtle text-success border border-success"
            record.change_summary_html = "Initial product creation."
        
        elif record.history_type == '-':
            record.action_label = "Deleted"
            record.badge_class = "bg-danger-subtle text-danger border border-danger"
            record.change_summary_html = "Product deleted."
        
        elif record.history_type == '~':
            if record.prev_record:
                delta = record.diff_against(record.prev_record)
                changes = []
                affected_fields = []
                
                for change in delta.changes:
                    field = change.field
                    old = change.old
                    new = change.new
                    
                    if field == 'price':
                        changes.append(f"<strong>Price:</strong> {old} &rarr; {new}")
                        affected_fields.append("Price")
                    elif field == 'quantity':
                        changes.append(f"<strong>Stock:</strong> {old} &rarr; {new}")
                        affected_fields.append("Stock")
                    elif field == 'status':
                        changes.append(f"<strong>Status:</strong> {old} &rarr; {new}")
                        affected_fields.append("Status")
                    elif field == 'category':
                        changes.append(f"<strong>Category</strong> updated")
                        affected_fields.append("Category")
                    elif field in ['slug', 'date_updated']:
                        continue
                    else:
                        changes.append(f"<strong>{field.replace('_', ' ').title()}:</strong> {old} &rarr; {new}")
                        affected_fields.append("Details")
                
                record.change_summary_html = "<br>".join(changes) if changes else "No specific field changes detected."
                
                unique_fields = list(set(affected_fields))
                if not unique_fields:
                    record.action_label = "Update"
                elif len(unique_fields) == 1:
                    record.action_label = unique_fields[0]
                else:
                    record.action_label = "Multiple"
                
                # Badge Colors
                if "Price" in unique_fields: record.badge_class = "bg-info-subtle text-info-emphasis border border-info"
                elif "Stock" in unique_fields: record.badge_class = "bg-warning-subtle text-warning-emphasis border border-warning"
                elif "Status" in unique_fields: record.badge_class = "bg-dark-subtle text-dark-emphasis border border-dark"
                elif "Category" in unique_fields: record.badge_class = "bg-primary-subtle text-primary border border-primary"
            else:
                record.change_summary_html = "No previous record for comparison."

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
        queryset = queryset.order_by('-history_date')
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
            
            # Handle Action Filtering
            action = form.cleaned_data.get('action')
            if action:
                if action in ['+', '-', '~']:
                    queryset = queryset.filter(history_type=action)
                elif action in ['STOCK', 'STATUS', 'DETAILS', 'PRICE']:
                    # 1. Filter for updates in DB first
                    queryset = queryset.filter(history_type='~')
                    
                    # 2. Filter by specific change in Python
                    filtered_list = []
                    for record in queryset:
                        if record.prev_record:
                            delta = record.diff_against(record.prev_record)
                            changed = delta.changed_fields
                            
                            if action == 'STOCK' and 'quantity' in changed:
                                filtered_list.append(record)
                            elif action == 'STATUS' and 'status' in changed:
                                filtered_list.append(record)
                            elif action == 'PRICE' and 'price' in changed:
                                filtered_list.append(record)
                            elif action == 'DETAILS':
                                # Check if fields OTHER than the main ones changed
                                if any(f for f in changed if f not in ['quantity', 'status', 'price', 'slug', 'date_updated']):
                                    filtered_list.append(record)
                    return filtered_list

        return queryset
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProductHistoryFilterForm(self.request.GET)
        process_history_records(context['page_obj'])
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
        process_history_records(context['page_obj'])
        return context