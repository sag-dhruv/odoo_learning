# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from datetime import datetime, time


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    return_count = fields.Integer(string="Return Count", compute="action_sale_return_ids_count")

    def action_sale_return_ids_count(self):
        self.return_count = self.env['sale.return.order'].sudo().search_count([('reference', '=', self.name)])

    def action_sale_return(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        form_view = self.sudo().env.ref('sale_return_form_view')
        tree_view = self.sudo().env.ref('sale_return_tree_view')
        return {
            'name': _('Return Sale Order'),
            'res_model': 'sale.return.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('reference', '=', self.name)],
        }

    def sale_return_button(self):
        view_id = self.env['sale.return.wizard']
        order_line = []
        if self.order_line:
            for i in self.order_line:
                vals = (0, 0, {
                    'product_id': i.product_id.id,
                    'onhand_qty': i.product_id.qty_available,
                    'quantity': i.product_uom_qty,
                    'price_unit': i.price_unit,
                    'price_subtotal': i.product_uom_qty * i.price_unit,
                })
                order_line.append(vals)
        ctx = {
            'default_partner_id': self.partner_id.id,
            'default_return_lines': order_line,
        }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Return',
            'res_model': 'sale.return.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': view_id.id,
            'view_id': self.env.ref('sale_return_related_wizard',
                                    False).id,
            'context': ctx,
            'target': 'new',
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    return_products = fields.Float(string='Return')
    sale_products = fields.Float(string='Return')

    @api.onchange('product_uom_qty', )
    def onchange_qty(self):
        self.write({
            'sale_products': self.product_uom_qty
        })

    @api.onchange('sale_products')
    def onchange_sale_products(self):
        self.write({
            'return_products': self.product_uom_qty - self.sale_products
        })

    # @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'sale_products', 'return_products')
    # def _compute_amount(self):
    #     """
    #     Compute the amounts of the SO line.
    #     """
    #     for line in self:
    #         price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
    #         taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty,
    #                                         product=line.product_id, partner=line.order_id.partner_shipping_id)
    #
    #         tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
    #         tax_included = taxes['total_included']
    #         tax_excluded = taxes['total_excluded']
    #         sub_total = line.sale_products * line.price_unit
    #         line.update({
    #             'price_tax': tax,
    #             'price_total': price,
    #             'price_subtotal': sub_total,
    #         })
    #         if self.env.context.get('import_file', False) and not self.env.user.user_has_groups(
    #                 'account.group_account_manager'):
    #             line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])
