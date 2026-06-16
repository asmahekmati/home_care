/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.HomeCareInvoiceModal = publicWidget.Widget.extend({
    selector: '.o_home_care_invoice_modal_form',
    events: {
        'click .hc-add-invoice-line': '_onAddLine',
        'click .hc-remove-invoice-line': '_onRemoveLine',
        'change .hc-line-product': '_onProductChange',
        'change .hc-tax-tags-picker': '_onTaxPickerChange',
        'click .hc-tax-tag-remove': '_onTaxTagRemove',
    },

    start() {
        this.$('.hc-invoice-line').each((_, line) => {
            this._initTaxTags($(line));
        });
        this._reindexLines();
        this.el.addEventListener('submit', () => this._reindexLines());
        return this._super(...arguments);
    },

    _reindexLines() {
        this.$('.hc-invoice-line').each((i, el) => {
            const $line = $(el);
            $line.find('[name^="line_"]').each((_, field) => {
                const name = $(field).attr('name');
                const suffix = name.substring(name.indexOf('_', 5));
                $(field).attr('name', 'line_' + i + suffix);
            });
            this._syncTaxHiddenInputs($line, i);
        });
    },

    _initTaxTags($line) {
        const $tags = $line.find('.hc-tax-tags');
        if (!$tags.length) {
            return;
        }
        $tags.each((_, tagRoot) => {
            const $root = $(tagRoot);
            $root.find('.hc-tax-tags-picker option').each((__, option) => {
                const $option = $(option);
                const taxId = $option.val();
                if (taxId && $root.find('.hc-tax-tag[data-tax-id="' + taxId + '"]').length) {
                    $option.prop('hidden', true);
                }
            });
        });
    },

    _syncTaxHiddenInputs($line, lineIndex) {
        const $tags = $line.find('.hc-tax-tags');
        if (!$tags.length) {
            return;
        }
        const prefix = 'line_' + lineIndex + '_tax_ids';
        $tags.each((_, tagRoot) => {
            const $root = $(tagRoot);
            const $hidden = $root.find('.hc-tax-tags-hidden');
            $hidden.empty();
            $root.find('.hc-tax-tag').each((__, tag) => {
                const taxId = $(tag).data('taxId');
                if (taxId) {
                    $hidden.append(
                        $('<input>', { type: 'hidden', name: prefix, value: taxId })
                    );
                }
            });
        });
    },

    _getTaxName($line, taxId) {
        const $option = $line.find('.hc-tax-tags-picker option[value="' + taxId + '"]');
        return $option.length ? $option.text().trim() : taxId;
    },

    _addTaxTag($line, taxId) {
        if (!taxId) {
            return;
        }
        const $tags = $line.find('.hc-tax-tags').first();
        const $list = $tags.find('.hc-tax-tags-list');
        if ($list.find('.hc-tax-tag[data-tax-id="' + taxId + '"]').length) {
            return;
        }
        const taxName = this._getTaxName($line, taxId);
        const $tag = $(
            '<span class="hc-tax-tag"/>'
        ).attr('data-tax-id', taxId).append(
            $('<button type="button" class="hc-tax-tag-remove" title="حذف" aria-label="حذف">×</button>'),
            $('<span class="hc-tax-tag-label"/>').text(taxName)
        );
        $list.append($tag);
        $tags.find('.hc-tax-tags-picker option[value="' + taxId + '"]').prop('hidden', true);
        $tags.find('.hc-tax-tags-picker').val('');
    },

    _removeTaxTag($line, taxId) {
        const $tags = $line.find('.hc-tax-tags').first();
        $tags.find('.hc-tax-tag[data-tax-id="' + taxId + '"]').remove();
        $tags.find('.hc-tax-tags-picker option[value="' + taxId + '"]').prop('hidden', false);
    },

    _clearTaxTags($line) {
        const $tags = $line.find('.hc-tax-tags').first();
        $tags.find('.hc-tax-tag').each((_, tag) => {
            const taxId = $(tag).data('taxId');
            $tags.find('.hc-tax-tags-picker option[value="' + taxId + '"]').prop('hidden', false);
        });
        $tags.find('.hc-tax-tags-list').empty();
        $tags.find('.hc-tax-tags-picker').val('');
        $tags.find('.hc-tax-tags-hidden').empty();
    },

    _setTaxesFromProduct($select) {
        const taxIds = ($select.find(':selected').data('taxIds') || '').toString();
        const $line = $select.closest('.hc-invoice-line');
        this._clearTaxTags($line);
        if (!taxIds) {
            this._reindexLines();
            return;
        }
        for (const id of taxIds.split(',').filter(Boolean)) {
            this._addTaxTag($line, id);
        }
        this._reindexLines();
    },

    _onTaxPickerChange(ev) {
        const $picker = $(ev.currentTarget);
        const taxId = $picker.val();
        if (!taxId) {
            return;
        }
        const $line = $picker.closest('.hc-invoice-line');
        this._addTaxTag($line, taxId);
        this._reindexLines();
    },

    _onTaxTagRemove(ev) {
        ev.preventDefault();
        const $tag = $(ev.currentTarget).closest('.hc-tax-tag');
        const taxId = $tag.data('taxId');
        const $line = $tag.closest('.hc-invoice-line');
        this._removeTaxTag($line, taxId);
        this._reindexLines();
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
        this._clearTaxTags($clone);
        $clone.find('.hc-tax-tags-picker option').prop('hidden', false);
        this.$('.hc-invoice-lines').append($clone);
        this._initTaxTags($clone);
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
