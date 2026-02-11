# inventory/serializers.py

from rest_framework import serializers
from .models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class ProductSerializer(serializers.ModelSerializer):
    # Show the category name (Read Only) for better API readability
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 
            'name', 
            'sku', 
            'image',
            'category',       # The ID (for writing/updating)
            'category_name',  # The Name (for reading/displaying)
            'price', 
            'quantity', 
            'reorder_level',
            'status',
            'last_purchase_date',
            'date_created', 
            'date_updated'
        ]