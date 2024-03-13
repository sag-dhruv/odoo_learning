from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleReturnWizard(models.TransientModel):
    _name = 'sale.return.wizard'
    _description = 'Sale Return Wizard'

    return_date = fields.Datetime(string='Date Of Return')
    partner_id = fields.Many2one('res.partner', string='Customer')
    user_name = fields.Many2one('res.users', string='Sale Representative')
    reason = fields.Char(string="Reason")
    return_lines = fields.One2many('sale.return.wizard.line', 'sale_wizard')

    def tick_ok(self):
        sale_return = self.env['sale.return.order']
        applicant_id = self._context.get('active_ids')[0]
        active_id = self.env['sale.order'].sudo().search([('id', '=', applicant_id)])
        if self.return_lines:
            for i in self.return_lines:
                if i.replace_qty <= 0.00:
                    raise UserError(_('Alert !! Dear %s, You have not entered the Replace Qty to Return '
                                      '\n Please Enter and try again') % self.env.user.name)
                if i.replace_qty > 0.00:
                    for j in active_id.order_line:
                        if i.product_id.id == j.product_id.id:
                            j.sale_products = i.qty
                            j.return_products = i.total_return
                            j.sale_products = i.qty
            return_line = [(5, 0, 0)]
            for i in self.return_lines:
                vals = {
                    'product_id': i.product_id.id,
                    'onhand_qty': i.replace_qty + i.qty,
                    'replace_qty': i.replace_qty,
                    'qty': i.qty,
                    'price_unit': i.price_unit,
                    'price_subtotal': i.price_subtotal,
                    'currency_id': i.currency_id,
                }
                return_line.append((0, 0, vals))

            datas = {
                'representative': self.user_name.id,
                'partner_id': self.partner_id.id,
                # 'stock_picking_type': active_id.picking_type_id.id,
                'return_date': self.return_date,
                'reason': self.reason,
                'reference': active_id.name,
                'return_lines': return_line,
            }
            sale_return.sudo().create(datas)


class SaleReturnWizardLine(models.TransientModel):
    _name = 'sale.return.wizard.line'
    _description = 'Sale Return Wizard Line'

    sale_wizard = fields.Many2one('sale.return.wizard')
    product_id = fields.Many2one('product.product', string='Product')
    onhand_qty = fields.Float(string='OnHand')
    replace_qty = fields.Float(string='Replace')
    quantity = fields.Float(string='Quantity')
    total_return = fields.Float(string='Return')
    qty = fields.Float(string='Qty')
    price_unit = fields.Float('Unit Price')
    price_subtotal = fields.Monetary(string='Subtotal')
    currency_id = fields.Many2one('res.currency', string='Currency')

    @api.onchange('replace_qty')
    def onchange_replace_qty(self):
        if self.quantity:
            self.write({
                'qty': self.quantity - self.replace_qty
            })
            self.write({
                'total_return': self.quantity - self.qty
            })
            self.write({
                'price_subtotal': self.replace_qty * self.price_unit
            })
