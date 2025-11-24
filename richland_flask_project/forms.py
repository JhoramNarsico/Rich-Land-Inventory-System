# forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired # <--- Added for File Upload
from wtforms import (StringField, PasswordField, SubmitField, DecimalField, 
                     IntegerField, SelectField, TextAreaField, FieldList, 
                     FormField, HiddenField, DateField, BooleanField)
from wtforms.validators import DataRequired, NumberRange, Optional, Email, EqualTo
from database import categories_collection 
from wtforms import SelectField 


# ==============================================================================
# Authentication Forms
# ==============================================================================

class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ChangePasswordForm(FlaskForm):
    """Form for users to change their own password."""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField('Update Password')

# ==============================================================================
# User Management Forms
# ==============================================================================

class UserRegistrationForm(FlaskForm):
    """Form for creating a new user account."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    group = SelectField('Role/Group', choices=[
        ('Salesman', 'Salesman'),
        ('Stock Manager', 'Stock Manager'),
        ('Admin', 'Admin'),
        ('Owner', 'Owner')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Account')

class UserEditForm(FlaskForm):
    """Form for the Owner to edit other users (Promote/Demote/Reset Password)."""
    username = StringField('Username', validators=[DataRequired()])
    group = SelectField('Role/Group', choices=[
        ('Salesman', 'Salesman'),
        ('Stock Manager', 'Stock Manager'),
        ('Admin', 'Admin'),
        ('Owner', 'Owner')
    ], validators=[DataRequired()])
    
    # Specific Permission Overrides
    perm_analytics = BooleanField('Grant Access to Analytics')
    perm_admin = BooleanField('Grant Access to Admin Panel')
    perm_history = BooleanField('Grant Access to Edit History')
    
    # Password is optional here
    password = PasswordField('New Password (Leave blank to keep current)', validators=[Optional()])
    submit = SubmitField('Update User')

# ==============================================================================
# Product Management Forms
# ==============================================================================

class ProductCreateForm(FlaskForm):
    """Form for creating a new product."""
    sku = StringField('SKU (Unique Identifier)', validators=[DataRequired()])
    name = StringField('Product Name', validators=[DataRequired()])
    category = SelectField('Category', coerce=str, validators=[Optional()]) 
    price = DecimalField('Price (PHP)', validators=[DataRequired(), NumberRange(min=0)])
    quantity = IntegerField('Initial Quantity', validators=[DataRequired(), NumberRange(min=0)])
    reorder_level = IntegerField('Reorder Level', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Save Product')

class ProductUpdateForm(FlaskForm):
    """Form for updating an existing product's details."""
    name = StringField('Product Name', validators=[DataRequired()])
    category = SelectField('Category', coerce=str, validators=[Optional()]) 
    price = DecimalField('Price (PHP)', validators=[DataRequired(), NumberRange(min=0)])
    reorder_level = IntegerField('Reorder Level', validators=[DataRequired(), NumberRange(min=1)])
    status = SelectField('Status', choices=[('ACTIVE', 'Active'), ('DEACTIVATED', 'Deactivated')], validators=[DataRequired()])
    submit = SubmitField('Update Product')

class ProductImportForm(FlaskForm):
    """Form to upload a CSV file for bulk product import."""
    csv_file = FileField('Upload CSV File', validators=[
        FileRequired(),
        FileAllowed(['csv'], 'CSV Files Only!')
    ])
    submit = SubmitField('Upload and Process')

class StockTransactionForm(FlaskForm):
    """Form for adjusting stock (IN or OUT)."""
    transaction_type = SelectField('Transaction Type', choices=[('IN', 'Stock In'), ('OUT', 'Stock Out')], validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1, message="Quantity must be at least 1.")])
    notes = TextAreaField('Notes (Optional)')
    submit = SubmitField('Record Adjustment')

# ==============================================================================
# Supplier Management Forms
# ==============================================================================

class SupplierForm(FlaskForm):
    """Form for creating and editing a supplier."""
    name = StringField('Supplier Name', validators=[DataRequired()])
    contact_person = StringField('Contact Person')
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    submit = SubmitField('Save Supplier')

# ==============================================================================
# Purchase Order Management Forms
# ==============================================================================

class PurchaseOrderItemForm(FlaskForm):
    """Sub-form for a single item within a purchase order."""
    class Meta:
        csrf = False
    product_sku = StringField('Product SKU', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])

class PurchaseOrderForm(FlaskForm):
    """Main form for creating a purchase order."""
    supplier = SelectField('Supplier', coerce=str, validators=[DataRequired()])
    items = FieldList(FormField(PurchaseOrderItemForm), min_entries=1)
    submit = SubmitField('Create Purchase Order')

# ==============================================================================
# Filter & History Forms
# ==============================================================================

class ProductFilterForm(FlaskForm):
    """Form for filtering the product list view."""
    q = StringField('Search by Name/SKU', validators=[Optional()])
    category = StringField('Filter by Category', validators=[Optional()]) 
    product_status = SelectField('Product Status', choices=[('', 'All Statuses'), ('ACTIVE', 'Active'), ('DEACTIVATED', 'Deactivated')], validators=[Optional()])
    sort_by = SelectField('Sort By', choices=[('-date_created', 'Newest First'), ('date_created', 'Oldest First'), ('name', 'Name (A-Z)'), ('-name', 'Name (Z-A)')], validators=[Optional()])
    submit = SubmitField('Apply')

class TransactionFilterForm(FlaskForm):
    """Form for filtering the transaction log."""
    product = StringField('Filter by Product SKU', validators=[Optional()])
    transaction_type = SelectField('Type', choices=[('', 'All Types'), ('IN', 'Stock In'), ('OUT', 'Stock Out')], validators=[Optional()])
    submit = SubmitField('Apply')

class ProductHistoryFilterForm(FlaskForm):
    """Form for filtering the product history log."""
    product_sku = StringField('Filter by Product SKU', validators=[Optional()])
    user = StringField('Filter by User', validators=[Optional()])
    submit = SubmitField('Apply Filters')

class SalesReportForm(FlaskForm):
    """Form for selecting a date range for the sales report."""
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])
    submit = SubmitField('Generate PDF Report')

class POFilterForm(FlaskForm):
    """Form for filtering the Purchase Order list."""
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])
    status = SelectField('Status', choices=[('', 'All Statuses'), ('PENDING', 'Pending'), ('COMPLETED', 'Completed')], validators=[Optional()])
    submit = SubmitField('Apply Filters')

class CategoryForm(FlaskForm):
    """Form to add a new category."""
    name = StringField('Category Name', validators=[DataRequired()])
    submit = SubmitField('Save Category')