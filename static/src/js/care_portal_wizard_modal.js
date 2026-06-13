/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.HomeCareInvoiceWizardModal = publicWidget.Widget.extend({
    selector: '.o_home_care_provider_detail',

    events: {
        'click .o_home_care_open_invoice_wizard': '_onOpenWizard',
    },

    _onOpenWizard(ev) {
        ev.preventDefault();
        const requestId = ev.currentTarget.dataset.requestId;
        if (!requestId) {
            return;
        }
        const modalEl = document.getElementById('careInvoiceWizardModal');
        const iframe = document.getElementById('careInvoiceWizardFrame');
        if (!modalEl || !iframe) {
            return;
        }
        iframe.src = 'about:blank';
        const Modal = window.Modal;
        if (!Modal) {
            iframe.src = `/my/care/provider/requests/${requestId}/invoice/wizard/embed`;
            return;
        }
        Modal.getOrCreateInstance(modalEl).show();
        iframe.src = `/my/care/provider/requests/${requestId}/invoice/wizard/embed`;
    },

    start() {
        const modalEl = document.getElementById('careInvoiceWizardModal');
        if (modalEl) {
            modalEl.addEventListener('hidden.bs.modal', () => {
                const iframe = document.getElementById('careInvoiceWizardFrame');
                if (iframe) {
                    iframe.src = 'about:blank';
                }
            });
        }
        return this._super(...arguments);
    },
});
