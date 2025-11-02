# inventory/forms.py
from django import forms
from django.contrib.auth.models import User
from django.forms import DateInput
from .models import Product, StockTransaction, Category

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'price', 'quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class StockTransactionForm(forms.ModelForm):
    class Meta:
        model = StockTransaction
        fields = ['transaction_type', 'quantity', 'notes']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ProductFilterForm(forms.Form):
    STOCK_STATUS_CHOICES = (
        ("", "All Statuses"),
        ("in_stock", "In Stock (>10)"),
        ("low_stock", "Low Stock (1-10)"),
        ("out_of_stock", "Out of Stock"),
    )
    SORT_BY_CHOICES = (
        ("-date_created", "Newest First"),
        ("date_created", "Oldest First"),
        ("name", "Name (A-Z)"),
        ("-name", "Name (Z-A)"),
        ("price", "Price (Low to High)"),
        ("-price", "Price (High to Low)"),
    )
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, label="Category", widget=forms.Select(attrs={'class': 'form-select'}))
    stock_status = forms.ChoiceField(choices=STOCK_STATUS_CHOICES, required=False, label="Stock Status", widget=forms.Select(attrs={'class': 'form-select'}))
    sort_by = forms.ChoiceField(choices=SORT_BY_CHOICES, required=False, label="Sort By", widget=forms.Select(attrs={'class': 'form-select'}))

class TransactionFilterForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), required=False, label="Product", widget=forms.Select(attrs={'class': 'form-select'}))
    transaction_type = forms.ChoiceField(choices=(("", "All Types"), ("IN", "Stock In"), ("OUT", "Stock Out")), required=False, label="Type", widget=forms.Select(attrs={'class': 'form-select'}))
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False, label="User", widget=forms.Select(attrs={'class': 'form-select'}))
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False)

# --- NEW FORM FOR THE REPORTING PAGE ---
class TransactionReportForm(forms.Form):
    start_date = forms.DateField(
        required=False, 
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False, 
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )