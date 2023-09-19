/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { sprintf } from "@web/core/utils/strings";
import { useSelectCreate, useOpenMany2XRecord} from "@web/views/fields/relational_utils";
export class SMLX2ManyField extends X2ManyField {
    setup() {
        super.setup();

        const selectCreate = useSelectCreate({
            resModel: "stock.quant",
            activeActions: this.activeActions,
            onSelected: (resIds) => this.selectRecord(resIds),
            onCreateEdit: () => this.createOpenRecord(),
        });

        this.selectCreate = (params) => {
            return selectCreate(params);
        };
        this.openRecord = useOpenMany2XRecord({
            resModel: "stock.quant",
            activeActions: this.activeActions,
            onRecordSaved: (resId) => this.selectRecord([resId.data.id]),
            onRecordDiscarted: (resId) => this.selectRecord(resId),
            fieldString: this.props.string,
            is2Many: true,
        });
    }

    async onAdd({ context, editable } = {}) {
        if(!this.props.context.use_create_lots && !this.props.context.use_existing_lots)
        {
            this.env.services.notification.add(
                this.env._t("Use existing lots and create new is disabled"),
                {type: 'danger'}
            );
        }
        context = {
            ...context,
            single_product: true,
            tree_view_ref: "stock.view_stock_quant_tree_simple",
        };
        const productName = this.props.record.data.product_id[1];
        const title = sprintf(this.env._t("Add line: %s"), productName);
        const alreadySelected = this.props.record.data.move_line_ids.records.filter((line) => line.data.quant_id?.[0]);
        const domain = [
            ["product_id", "=", this.props.record.data.product_id[0]],
            ["location_id", "child_of", this.props.context.default_location_id],
        ];
        if (alreadySelected.length) {
            domain.push(["id", "not in", alreadySelected.map((line) => line.data.quant_id[0])]);
        }
        return this.selectCreate({ domain, context, title });
    }

    selectRecord(res_ids) {
        const params = {
            context: { default_quant_id: res_ids[0] },
        };
        if(!this.props.context.use_existing_lots){
            this.env.services.notification.add(
                this.env._t("Use existing lots is disabled"),
                {type: 'danger'}
            );
        }
        else{
            this.addInLine(params);
        }
    }

    createOpenRecord() {
        const activeElement = document.activeElement;
        if(this.props.context.use_create_lots && this.props.context.use_existing_lots){
            this.openRecord({
                context: {
                    ...this.props.context,
                    form_view_ref: "stock.view_stock_quant_form",
                },
                immediate: true,
                onClose: () => {
                    if (activeElement) {
                        activeElement.focus();
                    }
                },
            });
        }
        else if(this.props.context.use_create_lots) {
            this.openRecord({
                context: {
                    ...this.props.context,
                    
                    form_view_ref: "stock.view_stock_quant_form",
                },
                immediate: true,
                onClose: () => {
                    if (activeElement) {
                        activeElement.focus();
                    }
                },
            });  
        }
        else{
            this.env.services.notification.add(
                this.env._t("Create new lot is disabled"),
                {type: 'danger'}
           );
        }       
    }
}

export const smlX2ManyField = {
    ...x2ManyField,
    component: SMLX2ManyField,
};

registry.category("fields").add("sml_x2_many", smlX2ManyField);
