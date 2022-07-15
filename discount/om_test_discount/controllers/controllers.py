# -*- coding: utf-8 -*-
# from odoo import http


# class OmTestDiscount(http.Controller):
#     @http.route('/om_test_discount/om_test_discount/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/om_test_discount/om_test_discount/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('om_test_discount.listing', {
#             'root': '/om_test_discount/om_test_discount',
#             'objects': http.request.env['om_test_discount.om_test_discount'].search([]),
#         })

#     @http.route('/om_test_discount/om_test_discount/objects/<model("om_test_discount.om_test_discount"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('om_test_discount.object', {
#             'object': obj
#         })
