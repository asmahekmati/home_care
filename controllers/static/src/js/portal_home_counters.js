/** @odoo-module **/

import { PortalHomeCounters } from "@portal/interactions/portal_home_counters";
import { patch } from "@web/core/utils/patch";

patch(PortalHomeCounters.prototype, {
    getCountersAlwaysDisplayed() {
        return super.getCountersAlwaysDisplayed(...arguments).concat([
            'care_request_count',
        ]);
    },
});
