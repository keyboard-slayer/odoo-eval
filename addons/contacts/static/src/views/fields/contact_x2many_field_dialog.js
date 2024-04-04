import { X2ManyFieldDialog } from "@web/views/fields/relational_utils";
import { patch } from "@web/core/utils/patch";

patch(X2ManyFieldDialog.prototype, {
    async moreOption() {
        let context = {};
        if (this.record.resId) {
            await this.record.save();
        } else {
            context = this.getDefaultValuesFromRecord(this.record.data, this.archInfo.fields);
        }
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: this.record.resModel,
            views: [[false, "form"]],
            res_id: this.record.resId || false,
            context: context,
        });
    },

    getDefaultValuesFromRecord(data, fields) {
        const context = {};
        for (let fieldName in fields) {
            if (fieldName in data) {
                let value = data[fieldName];
                const { type } = fields[fieldName];
                if (type === "many2one") {
                    value = value[0];
                }
                context[`default_${fieldName}`] = value || false;
            }
        }
        return context;
    },
});
