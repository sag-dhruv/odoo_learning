from odoo import fields, models, api


class SaleOrderReturnLine(models.TransientModel):
    _name = 'sale.order.return.line.wizard'

    sale_wizard = fields.Many2one('sale.order.return.wizard')
    product_id = fields.Many2one('product.product', string="Product")
    onhand_qty = fields.Float(string='OnHand')
    # qty_delivered = fields.Float(string="Delivered")
    replace_qty = fields.Float(string='Return')
    quantity = fields.Float(string='Quantity')
    total_return = fields.Float(string='Total Return')
    qty = fields.Float(string='Qty')
    currency_id = fields.Many2one('res.currency', string='Currency')
    price_unit = fields.Float(string="Unit Price")
    price_subtotal = fields.Monetary(string="Subtotal",compute='_compute_sub_total',)


    @api.onchange('replace_qty')
    def onchange_replace_qty(self):
        if self.quantity:
            self.write({
                'qty': self.quantity - self.replace_qty
            })
            self.write({
                'price_subtotal': self.replace_qty * self.price_unit
            })


class SaleOrderReturn(models.TransientModel):
    _name = 'sale.order.return.wizard'
    _description = 'Sale Return Wizard'

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderReturn, self).default_get(fields)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'sale.order':
            sale_order_id = self.env['sale.order'].browse(self.env.context.get('active_id'))
            if sale_order_id.exists():
                order_line_list = []
                for line_id in sale_order_id.order_line:
                    order_line_list.append((0, 0, {'product_id': line_id.product_id.id,
                                                   'onhand_qty': line_id.product_id.qty_available,
                                                   'quantity': line_id.product_uom_qty,
                                                   'price_unit': line_id.price_unit,
                                                   'price_subtotal': line_id.product_uom_qty * line_id.price_unit,
                                                   'total_return': line_id.return_qty,
                                                   }))
                res.update({'sale_order_id': sale_order_id.id,
                            'partner_id': sale_order_id.partner_id.id,
                            'user_id': sale_order_id.user_id.id,
                            'sale_order_return_lines': order_line_list,
                            })
        return res

    sale_order_id = fields.Many2one('sale.order')
    partner_id = fields.Many2one('res.partner', 'Customer')
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Sale Representative")
    return_reason = fields.Char(string="Reason")
    return_date = fields.Datetime(string='Date of Return', required=True, default=fields.Datetime.now)
    sale_order_return_lines = fields.One2many('sale.order.return.line.wizard', 'sale_wizard')

    def create_return_order(self):
        sale_return = self.env['sale.return.order']
        print(self._context, 'contexttttttttttttt')
        applicant_id = self._context.get('active_ids')[0]
        active_id = self.env['sale.order'].sudo().search([('id', '=', applicant_id)])
        print(active_id, 'active idddddddddddddddddddddddddd')
        if self.return_lines:
            for i in self.return_lines:
                print(i, 'iiiiiiiiiiiiiiiiiiii')
                if i.replace_qty <= 0.00:
                    raise UserError(_('Alert !! Dear %s, You have not entered the Replace Qty to Return '
                                      '\n Please Enter and try again') % self.env.user.name)
                if i.replace_qty > 0.00:
                    for j in active_id.order_line:
                        if i.product_id.id == j.product_id.id:
                            j.sale_products = i.qty
                            j.return_products = i.total_return + j.return_products
                            # j.sale_products = i.qty
            # print(absbdsabd)
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
                print(return_line, 'return line male 6')
            # print(asasasa,'datassssssssssssssssssssssss')
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


