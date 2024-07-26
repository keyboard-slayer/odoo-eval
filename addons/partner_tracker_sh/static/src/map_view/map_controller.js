/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { useModel } from "@web/views/model";
import { standardViewProps } from "@web/views/standard_view_props";
import { useSetupView } from "@web/views/view_hook";
import { Layout } from "@web/search/layout";
import { usePager } from "@web/search/pager_hook";

import { Component} from "@odoo/owl";

export class MapController extends Component {
    setup() {
        this.action = useService("action");

        /** @type {typeof MapModel} */
        const Model = this.props.Model;
        const model = useModel(Model, this.props.modelParams);
        this.model = model;

        useSetupView({
            getLocalState: () => {
                return this.model.metaData;
            },
        });

        usePager(() => {
            return {
                offset: this.model.metaData.offset,
                limit: this.model.metaData.limit,
                total: this.model.data.count,
                onUpdate: ({ offset, limit }) => this.model.load({ offset, limit }),
            };
        });
    }

    /**
     * @returns {any}
     */
    get rendererProps() {
        return {
            model: this.model,
            onMarkerClick: this.openRecords.bind(this),
        };
    }
 
    /**
     * Redirects to views when clicked on open button in marker popup.
     *
     * @param {number[]} ids
     */
    openRecords(ids) {
        if (ids.length > 1) {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: this.env.config.getDisplayName() || this.env._t("Untitled"),
                views: [
                    [false, "list"],
                    [false, "form"],
                ],
                res_model: this.props.resModel,
                domain: [["id", "in", ids]],
            });
        } else {
            this.action.switchView("form", { resId: ids[0] });
        }
    }
}

MapController.template = "partner_tracker.MapView";

MapController.components = {
    Layout,
};

MapController.props = {
    ...standardViewProps,
    Model: Function,
    modelParams: Object,
    Renderer: Function,
};
