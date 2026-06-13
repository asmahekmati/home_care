/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.HomeCareInvoiceModal = publicWidget.Widget.extend({
    selector: '.o_home_care_invoice_modal_form',
    events: {
        'click .hc-add-invoice-line': '_onAddLine',
        'click .hc-remove-invoice-line': '_onRemoveLine',
        'change .hc-line-product': '_onProductChange',
    },

    start() {
        this._reindexLines();
        return this._super(...arguments);
    },

    _reindexLines() {
        this.$('.hc-invoice-line').each((i, el) => {
            $(el).find('[name^="line_"]').each((_, field) => {
                const name = $(field).attr('name');
                const suffix = name.substring(name.indexOf('_', 5));
                $(field).attr('name', 'line_' + i + suffix);
            });
        });
    },

    _setTaxesFromProduct($select) {
        const taxIds = ($select.find(':selected').data('taxIds') || '').toString();
        if (!taxIds) {
            return;
        }
        const ids = taxIds.split(',').filter(Boolean);
        const $line = $select.closest('.hc-invoice-line');
        const $taxSelect = $line.find('.hc-line-taxes');
        $taxSelect.find('option').prop('selected', false);
        for (const id of ids) {
            $taxSelect.find('option[value="' + id + '"]').prop('selected', true);
        }
    },

    _onProductChange(ev) {
        const $select = $(ev.currentTarget);
        const price = $select.find(':selected').data('price');
        const $line = $select.closest('.hc-invoice-line');
        const $price = $line.find('.hc-line-price');
        if (price && $price.length) {
            $price.val(price);
        }
        this._setTaxesFromProduct($select);
    },

    _onAddLine(ev) {
        ev.preventDefault();
        const $clone = this.$('.hc-invoice-line').first().clone();
        $clone.find('input[type="text"], input[type="number"]').val('');
        $clone.find('input[name$="_quantity"]').val('1');
        $clone.find('input[name$="_discount"]').val('0');
        $clone.find('select.hc-line-product').prop('selectedIndex', 0);
        $clone.find('select.hc-line-taxes option').prop('selected', false);
        this.$('.hc-invoice-lines').append($clone);
        this._reindexLines();
    },

    _onRemoveLine(ev) {
        ev.preventDefault();
        if (this.$('.hc-invoice-line').length <= 1) {
            return;
        }
        $(ev.currentTarget).closest('.hc-invoice-line').remove();
        this._reindexLines();
    },
});
