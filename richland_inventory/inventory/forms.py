# inventory/forms.py
from django import forms
from django.contrib.auth.models import User
from django.forms import DateInput
from .models import Product, StockTransaction, Category, Supplier, PurchaseOrder

class ProductCreateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'price', 'quantity', 'reorder_level']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ProductUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'price', 'reorder_level', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class StockTransactionForm(forms.ModelForm):
    class Meta:
        model = StockTransaction
        fields = ['transaction_type', 'transaction_reason', 'quantity', 'notes']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'transaction_reason': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class StockOutForm(forms.ModelForm):
    class Meta:
        model = StockTransaction
        fields = ['transaction_reason', 'quantity', 'notes']
        widgets = {
            'transaction_reason': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g. Customer Name, Invoice #, or Reason for Damage'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        excluded_reasons = [
            StockTransaction.TransactionReason.PURCHASE_ORDER,
            StockTransaction.TransactionReason.RETURN,
            StockTransaction.TransactionReason.CORRECTION,
            StockTransaction.TransactionReason.INITIAL 
        ]
        valid_choices = [c for c in StockTransaction.TransactionReason.choices if c[0] not in excluded_reasons]
        self.fields['transaction_reason'].choices = valid_choices

class RefundForm(forms.ModelForm):
    class Meta:
        model = StockTransaction
        fields = ['quantity', 'notes']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for return (e.g. Defective, Wrong Item)'}),
        }

class ProductFilterForm(forms.Form):
    STOCK_STATUS_CHOICES = (("", "All Stock Levels"), ("in_stock", "In Stock (>10)"), ("low_stock", "Low Stock (1-10)"), ("out_of_stock", "Out of Stock"))
    PRODUCT_STATUS_CHOICES = (("ACTIVE", "Active"), ("DEACTIVATED", "Deactivated"), ("", "All Statuses"))
    SORT_BY_CHOICES = (("-date_created", "Newest First"), ("date_created", "Oldest First"), ("name", "Name (A-Z)"), ("-name", "Name (Z-A)"), ("price", "Price (Low to High)"), ("-price", "Price (High to Low)"))
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, label="Category", widget=forms.Select(attrs={'class': 'form-select'}))
    stock_status = forms.ChoiceField(choices=STOCK_STATUS_CHOICES, required=False, label="Stock Level", widget=forms.Select(attrs={'class': 'form-select'}))
    product_status = forms.ChoiceField(choices=PRODUCT_STATUS_CHOICES, required=False, label="Product Status", initial='ACTIVE', widget=forms.Select(attrs={'class': 'form-select'}))
    sort_by = forms.ChoiceField(choices=SORT_BY_CHOICES, required=False, label="Sort By", widget=forms.Select(attrs={'class': 'form-select'}))

# --- SEARCHABLE FILTER FORMS ---

class TransactionFilterForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        required=False, 
        label="Product", 
        # Added searchable-select
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Product...'})
    )
    transaction_type = forms.ChoiceField(choices=(("", "All Types"), ("IN", "Stock In"), ("OUT", "Stock Out")), required=False, label="Type", widget=forms.Select(attrs={'class': 'form-select'}))
    transaction_reason = forms.ChoiceField(choices=[('', 'All Reasons')] + list(StockTransaction.TransactionReason.choices), required=False, label="Reason", widget=forms.Select(attrs={'class': 'form-select'}))
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), 
        required=False, 
        label="User", 
        # Added searchable-select
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select User...'})
    )
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

class ProductHistoryFilterForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        required=False, 
        label="Product", 
        # Added searchable-select
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Product...'})
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), 
        required=False, 
        label="User", 
        # Added searchable-select
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select User...'})
    )
    
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

class PurchaseOrderFilterForm(forms.Form):
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(), 
        required=False, 
        label="Supplier", 
        # Added searchable-select
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Supplier...'})
    )
    
    status = forms.ChoiceField(choices=(("", "All Statuses"),) + PurchaseOrder.STATUS_CHOICES, required=False, label="Status", widget=forms.Select(attrs={'class': 'form-select'}))
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

class TransactionReportForm(forms.Form):
    start_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))

class CategoryCreateForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}

class AnalyticsFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))