# inventory/forms.py

from django import forms
from django.contrib.auth.models import User
from django.forms import DateInput
from .models import Product, StockTransaction, Category, Supplier, PurchaseOrder, Expense, ExpenseCategory
from .models import Customer, CustomerPayment
# --- PRODUCT MANAGEMENT FORMS ---

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address', 'tax_id', 'credit_limit']

class CustomerPaymentForm(forms.ModelForm):
    class Meta:
        model = CustomerPayment
        fields = ['amount', 'reference_number', 'notes']

class ProductCreateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'price', 'quantity', 'reorder_level']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Category...'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

class ProductUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'price', 'reorder_level', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Category...'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

# --- TRANSACTION FORMS ---

class StockTransactionForm(forms.ModelForm):
    """General form for admin usage"""
    class Meta:
        model = StockTransaction
        fields = ['transaction_type', 'transaction_reason', 'quantity', 'notes']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'transaction_reason': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class StockOutForm(forms.ModelForm):
    """
    Strictly for REMOVING stock (Sales, Damage, Internal Use).
    Filters out reasons that add stock (Returns, POs).
    """
    class Meta:
        model = StockTransaction
        fields = ['transaction_reason', 'quantity', 'notes']
        widgets = {
            'transaction_reason': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g. Customer Name, Invoice #, or Reason for Damage'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude reasons that don't make sense for a manual Stock Out
        excluded_reasons = [
            StockTransaction.TransactionReason.PURCHASE_ORDER,
            StockTransaction.TransactionReason.RETURN,
            StockTransaction.TransactionReason.CORRECTION,
            StockTransaction.TransactionReason.INITIAL 
        ]
        valid_choices = [c for c in StockTransaction.TransactionReason.choices if c[0] not in excluded_reasons]
        self.fields['transaction_reason'].choices = valid_choices

class RefundForm(forms.ModelForm):
    """Strictly for ADDING stock back (Returns)"""
    class Meta:
        model = StockTransaction
        fields = ['quantity', 'notes']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for return (e.g. Defective, Wrong Item)'}),
        }

# --- SEARCH/FILTER FORMS ---

class ProductFilterForm(forms.Form):
    STOCK_STATUS_CHOICES = (("", "All Stock Levels"), ("in_stock", "In Stock (>10)"), ("low_stock", "Low Stock (1-10)"), ("out_of_stock", "Out of Stock"))
    PRODUCT_STATUS_CHOICES = (("ACTIVE", "Active"), ("DEACTIVATED", "Deactivated"), ("", "All Statuses"))
    SORT_BY_CHOICES = (("-date_created", "Newest First"), ("date_created", "Oldest First"), ("name", "Name (A-Z)"), ("-name", "Name (Z-A)"), ("price", "Price (Low to High)"), ("-price", "Price (High to Low)"))
    
    q = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search Name or SKU...'})
    )
    
    # SEARCHABLE CATEGORY FILTER
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), 
        required=False, 
        label="Category", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Category...'})
    )
    
    stock_status = forms.ChoiceField(choices=STOCK_STATUS_CHOICES, required=False, label="Stock Level", widget=forms.Select(attrs={'class': 'form-select'}))
    product_status = forms.ChoiceField(choices=PRODUCT_STATUS_CHOICES, required=False, label="Product Status", initial='ACTIVE', widget=forms.Select(attrs={'class': 'form-select'}))
    sort_by = forms.ChoiceField(choices=SORT_BY_CHOICES, required=False, label="Sort By", widget=forms.Select(attrs={'class': 'form-select'}))

class TransactionFilterForm(forms.Form):
    # SEARCHABLE PRODUCT FILTER
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        required=False, 
        label="Product", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Product...'})
    )
    transaction_type = forms.ChoiceField(choices=(("", "All Types"), ("IN", "Stock In"), ("OUT", "Stock Out")), required=False, label="Type", widget=forms.Select(attrs={'class': 'form-select'}))
    transaction_reason = forms.ChoiceField(choices=[('', 'All Reasons')] + list(StockTransaction.TransactionReason.choices), required=False, label="Reason", widget=forms.Select(attrs={'class': 'form-select'}))
    
    # SEARCHABLE USER FILTER
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), 
        required=False, 
        label="User", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select User...'})
    )
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

class ProductHistoryFilterForm(forms.Form):
    # SEARCHABLE PRODUCT FILTER
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        required=False, 
        label="Product", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Product...'})
    )
    
    # SEARCHABLE USER FILTER
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), 
        required=False, 
        label="User", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select User...'})
    )
    
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

class PurchaseOrderFilterForm(forms.Form):
    # SEARCHABLE SUPPLIER FILTER
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(), 
        required=False, 
        label="Supplier", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Supplier...'})
    )
    
    status = forms.ChoiceField(choices=(("", "All Statuses"),) + PurchaseOrder.STATUS_CHOICES, required=False, label="Status", widget=forms.Select(attrs={'class': 'form-select'}))
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

# --- REPORTING FORMS ---

class TransactionReportForm(forms.Form):
    start_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))

class AnalyticsFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))

# --- MISC FORMS ---

class CategoryCreateForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}

# --- EXPENSE FORMS ---

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'description', 'amount', 'expense_date', 'receipt']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'expense_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'receipt': forms.FileInput(attrs={'class': 'form-control'}),
        }

class ExpenseFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search description...'}))
    category = forms.ModelChoiceField(queryset=ExpenseCategory.objects.all(), required=False, label="Category", widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'All Categories'}))
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)