from odoo import models, fields,api,_


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    sale_order_return_count = fields.Integer(string="Return Count", compute="compute_sale_return_count")
    
    @api.depends('name')
    def compute_sale_return_count(self):
        for rec in self:
            rec.sale_order_return_count = self.env['sale.order.return'].sudo().search_count([('reference', '=', self.name)])

    def action_sale_return(self):
        self.sudo().ensure_one()
        form_view = self.sudo().env.ref('app_development.sale_return_form_view')
        tree_view = self.sudo().env.ref('app_development.sale_return_tree_view')
        return {
            'name': _('Return Sale Order'),
            'res_model': 'sale.return.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('reference', '=', self.name)]
        }
    
	 # this method returns a wizard
    # def sale_return_button(self):
    #     view_id = self.env['sale.return.wizard']
    #     order_line = []
    #     if self.order_line:
    #         for i in self.order_line:
    #             vals = (0, 0, {
    #                 'product_id': i.product_id.id,
    #                 'onhand_qty': i.product_id.qty_available,
    #                 'quantity': i.product_uom_qty,
    #                 'price_unit': i.price_unit,
    #                 'price_subtotal': i.product_uom_qty * i.price_unit,
    #                 'total_return': i.return_products,
    #             })
    #             order_line.append(vals)
    #     ctx = {
    #         'default_partner_id': self.partner_id.id,
    #         'default_return_lines': order_line,
    #     }
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Sale Return',
    #         'res_model': 'sale.return.wizard',
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_id': view_id.id,
    #         'view_id': self.env.ref('sale_return_related_wizard',
    #                                 False).id,
    #         'context': ctx,
    #         'target': 'new',
    #     }

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    return_qty = fields.Float(string="Return")


