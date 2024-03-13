from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from datetime import datetime, time


class SaleReturnOrder(models.Model):
    _name = 'sale.return.order'
    _description = 'Sale Return Order'

    def _get_stock_type_ids(self):
        data = self.env['stock.picking.type'].search([])
        for line in data:
            if line.name == 'Receipts' and line.sequence_code == 'IN':
                self.stock_picking_type = line.id

    @api.model
    def create(self, vals):
        vals["name"] = (
                self.env["ir.sequence"].next_by_code("sale.return.order") or "New"
        )
        return super(SaleReturnOrder, self).create(vals)

    name = fields.Char(string='Name')
    partner_id = fields.Many2one('res.partner', string='Customer')
    representative = fields.Many2one('res.users', string=' Representative')
    return_date = fields.Datetime(string='Date Of Return')
    reason = fields.Char(string="Reason")
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed')], default='draft')
    reference = fields.Char(string='Reference')
    return_lines = fields.One2many('sale.return.order.line', 'sale_return_order')
    stock_picking_type = fields.Many2one('stock.picking.type', string='Operation Type', compute='_get_stock_type_ids')
    invoice_picking_id = fields.Many2one('stock.picking', string="Picking Id", copy=False)
    sale_return_confirm_ids = fields.Integer(string="Return", compute='sale_retrun_count')
    sale_return_invoice = fields.Integer(string="Credit Note", compute='sale_return_credit_note_count')
    accounts_move_id = fields.Many2one('account.move', string='Return')

    def action_sale_return_button_box(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        form_view = self.sudo().env.ref('stock.view_picking_form')
        tree_view = self.sudo().env.ref('stock.vpicktree')
        return {
            'name': _('Return Sale Order'),
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('origin', '=', self.name)],
        }

    def sale_retrun_count(self):
        count = self.env['stock.picking'].sudo().search_count([('origin', '=', self.name)])
        self.sale_return_confirm_ids = count

    def sale_return_credit_note_count(self):
        count = self.env['account.move'].sudo().search_count([('narration', '=', self.name)])
        self.sale_return_invoice = count

    def action_stock_move(self):
        if not self.stock_picking_type:
            raise UserError(_(
                " Please select a picking type"))
        for order in self:
            if not self.invoice_picking_id:
                pick = {}
                if self.stock_picking_type.code == 'incoming':
                    pick = {
                        'picking_type_id': order.stock_picking_type.id,
                        'partner_id': order.partner_id.id,
                        'origin': order.name,
                        'location_dest_id': order.stock_picking_type.default_location_dest_id.id,
                        'location_id': order.partner_id.property_stock_customer.id,
                        'move_type': 'direct',
                    }
                self.write({'state': 'confirm'})
                picking = self.env['stock.picking'].create(pick)
                self.invoice_picking_id = picking.id
                self.sale_return_confirm_ids = len(picking)
                moves = order.return_lines.filtered(
                    lambda r: r.product_id.type in ['product', 'consu'])._create_stock_moves(picking)
                print('---------------------------moves-----------------------------',moves)
                move_ids = moves._action_confirm()
                move_ids._action_assign()

    def create_customer_credit(self):
        """This is the function for creating customer credit note
                from the sales return"""
        if self.stock_picking_type.code == 'incoming':
            invoice_line_list = []
            for sale_returns in self.return_lines:
                vals = (0, 0, {
                    'name': sale_returns.product_id.name,
                    'product_id': sale_returns.product_id.id,
                    'price_unit': sale_returns.price_unit,
                    'account_id': sale_returns.product_id.property_account_income_id.id if sale_returns.product_id.property_account_income_id
                    else sale_returns.product_id.categ_id.property_account_income_categ_id.id,
                    'quantity': sale_returns.replace_qty,
                })
                invoice_line_list.append(vals)
            invoice = self.env['account.move'].sudo().create({
                'move_type': 'out_refund',
                'invoice_origin': self.name,
                'narration': self.name,
                'partner_id': self.partner_id.id,
                'currency_id': self.env.user.company_id.currency_id.id,
                'journal_id': 1,
                'payment_reference': self.name + '(' + self.reference + ')',
                'ref': self.name,
                'invoice_line_ids': invoice_line_list
            })
            return invoice

    def action_open_credit_invoice(self):
        """This is the function of the smart button which redirect to the
        invoice related to the current picking"""
        return {
            'name': 'Customer Credit Note Invoices',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'domain': [('narration', '=', self.name)],
            'context': {'create': False},
            'target': 'current'
        }



class SaleReturnOrderLine(models.Model):
    _name = 'sale.return.order.line'
    _description = 'Sale Return Order Line'

    sale_return_order = fields.Many2one('sale.return.order')
    product_id = fields.Many2one('product.product', string='Product')
    onhand_qty = fields.Float(string='OnHand')
    replace_qty = fields.Float(string='Replace')
    qty = fields.Float(string='Qty')
    price_unit = fields.Float('Unit Price')
    price_subtotal = fields.Monetary(string='Subtotal')
    currency_id = fields.Many2one('res.currency', string='Currency')

    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        for line in self:
            if picking.picking_type_id.code == 'incoming':
                template = {
                    'name': 'line.name or ''',
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_po_id.id,
                    'location_id': line.sale_return_order.partner_id.property_stock_supplier.id,
                    'location_dest_id': picking.picking_type_id.default_location_dest_id.id,
                    'picking_id': picking.id,
                    'state': 'draft',
                    # 'company_id': line.sale_return_order.company_id.id,
                    # 'price_unit': price_unit,
                    'picking_type_id': picking.picking_type_id.id,
                    'warehouse_id': picking.picking_type_id.warehouse_id.id,
                 # if you want know stock root (customize the below route code for your requirement)
                    # 'route_ids': 1 and [
                    #     (6, 0, [x.id for x in self.env['stock.location.route'].search([('id', 'in', (2, 3))])])] or [],


                }
            diff_quantity = line.replace_qty
            tmp = template.copy()
            tmp.update({
                'product_uom_qty': diff_quantity,
            })
            template['product_uom_qty'] = diff_quantity
            done += moves.create(template)
        return done


class AccountMove(models.Model):
    _inherit = 'account.move'

    picking_id = fields.Many2one('stock.picking', string='Picking')
