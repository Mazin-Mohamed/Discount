from odoo import api,fields,models,_

class AccountInvoice(models.Model):
    _inherit = "account.move"

    discount_type = fields.Selection([('percentage', ' Percentage '), ('amount', 'Amount')], string='Discount Type',
                                     default='percentage')
    percentage = fields.Float(string="Discount Percentage")
    amount = fields.Float(string="Discount Amount")
    amount_untaxed = fields.Float(string="Amount untaxed", compute="_amount_all", store=True)

    # @api.onchange('discount_type', 'percentage', 'amount',"invoice_line_ids")
    # def supply_rate(self):
    #     for rec in self:
    #         if rec.discount_type == 'amount':
    #             rec.amount_untaxed=rec.amount_untaxed - rec.amount
    #             rec._onchange_price_subtotal()
    #         else:
    #             if rec.amount_untaxed and rec.percentage:
    #                 discount=rec.amount_untaxed * rec.percentage/100
    #                 rec.amount_untaxed = rec.amount_untaxed - discount
    #                 rec.amount_total += rec.amount_untaxed
    #                 rec._onchange_price_subtotal()
    #         rec._compute_invoice_taxes_by_group()
    #
    #         rec.update({
    #             'amount_total': rec.amount_untaxed + rec.amount_tax,
    #         })

    # @api.onchange('discount_type', 'percentage', 'amount')
    # def supply_rate(self):
    #     result = super(AccountInvoice, self).supply_rate()
    #     for res in self:
    #         if res.discount_type == 'percentage':
    #             x= (res.percentage * res.amount_total)/100
    #             res.amount_total+=x
    #         else:
    #             y= res.amount - res.amount_total
    #             res.amount_total +=y
    #             # res.amount_total+=res.amount_residual
    #     return result


    def _madm(self):
        invoice_vals = super(AccountInvoice, self)._madm()
        invoice_vals.update({
            'discount_type': self.discount_type,
            'percentage': self.percentage,
            'amount': self.amount,
            'amount_total': self.amount_total,
        })
        return invoice_vals
    @api.model
    def _get_invoice_in_payment_state(self):
        ''' Hook to give the state when the invoice becomes fully paid. This is necessary because the users working
        with only invoicing don't want to see the 'in_payment' state. Then, this method will be overridden in the
        accountant module to enable the 'in_payment' state. '''
        return 'paid'

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.debit',
        'line_ids.credit',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id')
    def _compute_amount(self):
        for move in self:

            if move.payment_state == 'invoicing_legacy':
                # invoicing_legacy state is set via SQL when setting setting field
                # invoicing_switch_threshold (defined in account_accountant).
                # The only way of going out of this state is through this setting,
                # so we don't recompute it here.
                move.payment_state = move.payment_state
                continue

            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_to_pay = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = set()

            for line in move.line_ids:
                if line.currency_id and line in move._get_lines_onchange_currency():
                    currencies.add(line.currency_id)

                if move.is_invoice(include_receipts=True):
                    # === Invoices ===

                    if not line.exclude_from_invoice_tab:
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.tax_line_id:
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                        # Residual amount.
                        total_to_pay += line.balance
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            if move.move_type == 'entry' or move.is_outbound():
                sign = 1
            else:
                sign = -1
            move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
            move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual

            currency = len(currencies) == 1 and currencies.pop() or move.company_id.currency_id

            # Compute 'payment_state'.
            new_pmt_state = 'not_paid' if move.move_type != 'entry' else False

            if move.is_invoice(include_receipts=True) and move.state == 'posted':

                if currency.is_zero(move.amount_residual):
                    reconciled_payments = move._get_reconciled_payments()
                    if not reconciled_payments or all(payment.is_matched for payment in reconciled_payments):
                        new_pmt_state = 'paid'
                    else:
                        new_pmt_state = move._get_invoice_in_payment_state()
                elif currency.compare_amounts(total_to_pay, total_residual) != 0:
                    new_pmt_state = 'partial'

            if new_pmt_state == 'paid' and move.move_type in ('in_invoice', 'out_invoice', 'entry'):
                reverse_type = move.move_type == 'in_invoice' and 'in_refund' or move.move_type == 'out_invoice' and 'out_refund' or 'entry'
                reverse_moves = self.env['account.move'].search([('reversed_entry_id', '=', move.id), ('state', '=', 'posted'), ('move_type', '=', reverse_type)])

                # We only set 'reversed' state in cas of 1 to 1 full reconciliation with a reverse entry; otherwise, we use the regular 'paid' state
                reverse_moves_full_recs = reverse_moves.mapped('line_ids.full_reconcile_id')
                if reverse_moves_full_recs.mapped('reconciled_line_ids.move_id').filtered(lambda x: x not in (reverse_moves + reverse_moves_full_recs.mapped('exchange_move_id'))) == move:
                    new_pmt_state = 'reversed'

            move.payment_state = new_pmt_state

