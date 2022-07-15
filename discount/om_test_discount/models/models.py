
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    discount_type = fields.Selection([('percentage', ' Percentage '), ('amount', 'Amount')], string='Discount Type',
                                     default='percentage')
    percentage = fields.Float(string="Discount Percentage")
    amount = fields.Float(string="Discount Amount")
    amount_untaxed = fields.Float(string="Amount untaxed", compute="_amount_all", store=True)


    @api.onchange('discount_type', 'percentage', 'amount')
    def _amount_all(self):
        result = super(SaleOrder, self)._amount_all()
        for rec in self:
            if rec.discount_type == 'amount':
                rec.amount_untaxed=rec.amount_untaxed - rec.amount
            else:
                discount=rec.amount_untaxed * rec.percentage/100
                rec.amount_untaxed = rec.amount_untaxed - discount
                rec.amount_total += rec.amount_untaxed
            rec.update({
                'amount_total': rec.amount_untaxed + rec.amount_tax,
            })
        return result

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (self.company_id.name, self.company_id.id))

        invoice_vals = {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'narration': self.note,
            'currency_id': self.pricelist_id.currency_id.id,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'invoice_user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'discount_type': self.discount_type,
            'percentage': self.percentage,
            'amount': self.amount,
            'amount_total': self.amount_total,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id.get_fiscal_position(self.partner_invoice_id.id)).id,
            'partner_bank_id': self.company_id.partner_id.bank_ids[:1].id,
            'journal_id': journal.id,  # company comes from the journal
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'payment_reference': self.reference,
            'transaction_ids': [(6, 0, self.transaction_ids.ids)],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals
    def get_sale_order_reference(self):
        for rec in self:
            res = self.env['account.move'].search([('name', '=', 'amount_total')])
            rec.so_reference=res

    def action_invoice_open(self):
        res = super(SaleOrder, self).action_invoice_open()
        for inv in self:
            for inv_line in inv.invoice_line_ids:
                product = inv_line.product_id
                if product:
                    product.write({'standard_price': inv_line.price_unit})
        return res

    # def _prepare_invoice_line(self):
    #     res = super(SaleOrder, self)._prepare_invoice_line()
    #     res.update({'discount_type': self.discount_type, 'percentage': self.percentage,'amount': self.amount,'amount_untaxed': self.amount_untaxed})
    #     return res
    # def _paroaskfp(self):
    #     invoice_vals = super(SaleOrder, self)._paroaskfp()
    #     invoice_vals["amount_untaxed"]= self.amount_untaxed
    #     return invoice_vals
