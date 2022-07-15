from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
class Purchase_Order(models.Model):
    _inherit = "purchase.order"

    discount_type = fields.Selection([('percentage', ' Percentage '), ('amount', 'Amount')], string='Discount Type',
                                     default='percentage')
    percentage = fields.Float(string="Discount Percentage")
    amount = fields.Float(string="Discount Amount")
    amount_untaxed = fields.Float(string="Amount untaxed", compute="_amount_all", store=True)


    @api.depends('discount_type', 'percentage', 'amount')
    def _amount_all(self):
        result = super(Purchase_Order, self)._amount_all()
        for rec in self:
            if rec.discount_type == 'amount':
                rec.amount_untaxed=rec.amount_untaxed - rec.amount
            else:
                if rec.amount_untaxed and rec.percentage:
                    discount=rec.amount_untaxed * rec.percentage/100
                    rec.amount_untaxed = rec.amount_untaxed - discount
                    rec.amount_total += rec.amount_untaxed
            rec.update({
                'amount_total': rec.amount_untaxed + rec.amount_tax,
            })
        return result
    def _prepare_invoice(self):
        """Prepare the dict of values to create the new invoice for a purchase order.
        """
        self.ensure_one()
        move_type = self._context.get('default_move_type', 'in_invoice')
        journal = self.env['account.move'].with_context(default_move_type=move_type)._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting purchase journal for the company %s (%s).') % (self.company_id.name, self.company_id.id))

        partner_invoice_id = self.partner_id.address_get(['invoice'])['invoice']
        invoice_vals = {
            'ref': self.partner_ref or '',
            'move_type': move_type,
            'narration': self.notes,
            'currency_id': self.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id,
            'partner_id': partner_invoice_id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id.get_fiscal_position(partner_invoice_id)).id,
            'payment_reference': self.partner_ref or '',
            'partner_bank_id': self.partner_id.bank_ids[:1].id,
            'invoice_origin': self.name,
            'discount_type': self.discount_type,
            'percentage': self.percentage,
            'amount': self.amount,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals
