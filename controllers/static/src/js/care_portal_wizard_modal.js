/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.HomeCareInvoiceWizardModal = publicWidget.Widget.extend({
    selector: '.o_home_care_provider_detail',

    events: {
        'click .o_home_care_open_invoice_wizard': '_onOpenWizard',
    },

    _onOpenWizard(ev) {
        ev.preventDefault();
        const modalEl = document.getElementById('careInvoiceWizardModal');
        if (!modalEl) {
            return;
        }
        const Modal = window.Modal;
        if (Modal) {
            Modal.getOrCreateInstance(modalEl).show();
        }
    },
});
