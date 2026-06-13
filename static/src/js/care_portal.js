/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { rpc } from '@web/core/network/rpc';

publicWidget.registry.HomeCareRequestForm = publicWidget.Widget.extend({
    selector: '.o_home_care_request_form',
    events: {
        'change #care_request_type': '_onTypeChange',
        'change #care_entitlement_id': '_onEntitlementChange',
        'change input[name="patient_relation"]': '_onPatientRelationChange',
    },

    start() {
        this._onTypeChange();
        this._onPatientRelationChange();
        return this._super(...arguments);
    },

    _getPartnerPrefill() {
        const el = this.el;
        const name = (el.dataset.partnerName || '').trim();
        const parts = name.split(' ', 2);
        return {
            firstName: parts[0] || '',
            lastName: parts[1] || '',
            phone: el.dataset.partnerPhone || '',
            address: el.dataset.partnerAddress || '',
            nationalId: el.dataset.partnerNationalId || '',
        };
    },

    _setPatientField(id, value) {
        const field = this.el.querySelector('#' + id);
        if (field) {
            field.value = value || '';
        }
    },

    _clearPatientFields() {
        [
            'patient_first_name', 'patient_last_name', 'patient_national_id',
            'patient_phone', 'patient_mobile', 'patient_address',
        ].forEach((id) => this._setPatientField(id, ''));
        const age = this.el.querySelector('[name="patient_age"]');
        if (age) age.value = '';
        const gender = this.el.querySelector('[name="patient_gender"]');
        if (gender) gender.value = '';
        const caseCode = this.el.querySelector('[name="patient_case_code"]');
        if (caseCode) caseCode.value = '';
    },

    _prefillPatientFromPartner() {
        const data = this._getPartnerPrefill();
        this._setPatientField('patient_first_name', data.firstName);
        this._setPatientField('patient_last_name', data.lastName);
        this._setPatientField('patient_national_id', data.nationalId);
        this._setPatientField('patient_phone', data.phone);
        this._setPatientField('patient_mobile', data.phone);
        this._setPatientField('patient_address', data.address);
    },

    _onPatientRelationChange() {
        const relation = this.el.querySelector('input[name="patient_relation"]:checked')?.value;
        if (relation === 'self') {
            this._prefillPatientFromPartner();
        } else if (relation === 'other') {
            this._clearPatientFields();
        }
    },

    _onTypeChange() {
        const type = this.el.querySelector('#care_request_type')?.value;
        const packageBlock = this.el.querySelector('#care_package_block');
        const standaloneBlock = this.el.querySelector('#care_standalone_block');
        if (type === 'standalone') {
            packageBlock?.classList.add('d-none');
            standaloneBlock?.classList.remove('d-none');
        } else {
            packageBlock?.classList.remove('d-none');
            standaloneBlock?.classList.add('d-none');
        }
    },

    async _onEntitlementChange(ev) {
        const entitlementId = parseInt(ev.target.value, 10);
        const productSelect = this.el.querySelector('#care_product_id');
        if (!productSelect) {
            return;
        }
        productSelect.innerHTML = '<option value="">— انتخاب کنید —</option>';
        if (!entitlementId) {
            return;
        }
        const services = await rpc('/my/care/entitlement/' + entitlementId + '/services', {});
        for (const service of services) {
            const option = document.createElement('option');
            option.value = service.id;
            option.textContent = service.name + (service.category ? ' (' + service.category + ')' : '');
            productSelect.appendChild(option);
        }
    },
});
