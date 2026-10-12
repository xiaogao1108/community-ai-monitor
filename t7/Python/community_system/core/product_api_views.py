#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
商品管理REST API视图
为前端Vue.js提供商品相关的REST API接口
"""

import json
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from core.models import Product
from datetime import datetime
from .security import community_access

def api_products_select(request):
    """
    获取商品列表
    API: GET /api/products/select
    
    查询参数:
    - productName: 商品名称搜索
    - minPoints: 最小积分
    - maxPoints: 最大积分
    - pageNum: 页码 (默认1)
    - pageSize: 每页条数 (默认5)
    """
    try:
        # 获取查询参数
        product_name = request.GET.get('productName', '')
        min_points = request.GET.get('minPoints', '')
        max_points = request.GET.get('maxPoints', '')
        page_num = int(request.GET.get('pageNum', 1))
        page_size = int(request.GET.get('pageSize', 5))
        
        # 构建查询
        products = Product.objects.all()
        
        # 商品名称搜索
        if product_name:
            products = products.filter(
                Q(product_name__icontains=product_name) |
                Q(description1__icontains=product_name) |
                Q(description2__icontains=product_name)
            )
        
        # 积分范围筛选
        if min_points:
            products = products.filter(points_required__gte=int(min_points))
        if max_points:
            products = products.filter(points_required__lte=int(max_points))
        
        # 排序（按创建时间倒序）
        products = products.order_by('-created_at')
        
        # 分页
        paginator = Paginator(products, page_size)
        page_obj = paginator.get_page(page_num)
        
        # 构建响应数据
        product_list = []
        for product in page_obj:
            product_list.append({
                'productId': product.product_id,
                'productName': product.product_name,
                'pointsRequired': product.points_required,
                'description1': product.description1 or '',
                'description2': product.description2 or '',
                'imageUrl': product.image_url or '',
                'quantity': product.quantity,
                'createdAt': product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else ''
            })
        
        return JsonResponse({
            'state': 2001,
            'msg': '获取商品列表成功',
            'data': {
                'list': product_list,
                'totalPage': paginator.count,
                'pageNum': page_num,
                'pageSize': page_size
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'state': 4001,
            'msg': f'获取商品列表失败: {str(e)}',
            'data': None
        })

@community_access('admin', api=True)
def api_products_add(request):
    """
    添加商品
    API: POST /api/products/add
    """
    if request.method != 'POST':
        return JsonResponse({'state': 4001, 'msg': '只支持POST请求', 'data': None})
    
    try:
        data = json.loads(request.body)
        
        product = Product.objects.create(
            product_name=data.get('productName', ''),
            points_required=data.get('pointsRequired', 0),
            description1=data.get('description1', ''),
            description2=data.get('description2', ''),
            image_url=data.get('imageUrl', ''),
            quantity=data.get('quantity', 0)
        )
        
        return JsonResponse({
            'state': 2001,
            'msg': '商品添加成功',
            'data': {
                'productId': product.product_id,
                'productName': product.product_name
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'state': 4001,
            'msg': f'商品添加失败: {str(e)}',
            'data': None
        })

@community_access('admin', api=True)
def api_products_update(request):
    """
    更新商品
    API: PUT /api/products/update
    """
    if request.method != 'PUT':
        return JsonResponse({'state': 4001, 'msg': '只支持PUT请求', 'data': None})
    
    try:
        data = json.loads(request.body)
        product_id = data.get('productId')
        
        if not product_id:
            return JsonResponse({'state': 4001, 'msg': '商品ID不能为空', 'data': None})
        
        product = Product.objects.get(product_id=product_id)
        
        # 更新字段
        product.product_name = data.get('productName', product.product_name)
        product.points_required = data.get('pointsRequired', product.points_required)
        product.description1 = data.get('description1', product.description1)
        product.description2 = data.get('description2', product.description2)
        product.image_url = data.get('imageUrl', product.image_url)
        product.quantity = data.get('quantity', product.quantity)
        
        product.save()
        
        return JsonResponse({
            'state': 2001,
            'msg': '商品更新成功',
            'data': {
                'productId': product.product_id,
                'productName': product.product_name
            }
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'state': 4001,
            'msg': '商品不存在',
            'data': None
        })
    except Exception as e:
        return JsonResponse({
            'state': 4001,
            'msg': f'商品更新失败: {str(e)}',
            'data': None
        })

@community_access('admin', api=True)
def api_products_delete(request, product_id):
    """
    删除商品
    API: DELETE /api/products/delete/id/{product_id}
    """
    if request.method != 'DELETE':
        return JsonResponse({'state': 4001, 'msg': '只支持DELETE请求', 'data': None})
    
    try:
        product = Product.objects.get(product_id=product_id)
        product_name = product.product_name
        product.delete()
        
        return JsonResponse({
            'state': 2001,
            'msg': '商品删除成功',
            'data': {
                'productId': product_id,
                'productName': product_name
            }
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'state': 4001,
            'msg': '商品不存在',
            'data': None
        })
    except Exception as e:
        return JsonResponse({
            'state': 4001,
            'msg': f'商品删除失败: {str(e)}',
            'data': None
        })

def api_products_select_by_id(request, product_id):
    """
    根据ID获取商品详情
    API: GET /api/products/select/id/{product_id}
    """
    try:
        product = Product.objects.get(product_id=product_id)
        
        product_data = {
            'productId': product.product_id,
            'productName': product.product_name,
            'pointsRequired': product.points_required,
            'description1': product.description1 or '',
            'description2': product.description2 or '',
            'imageUrl': product.image_url or '',
            'quantity': product.quantity,
            'createdAt': product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else ''
        }
        
        return JsonResponse({
            'state': 2001,
            'msg': '获取商品详情成功',
            'data': product_data
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'state': 4001,
            'msg': '商品不存在',
            'data': None
        })
    except Exception as e:
        return JsonResponse({
            'state': 4001,
            'msg': f'获取商品详情失败: {str(e)}',
            'data': None
        })
