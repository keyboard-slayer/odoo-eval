/** @odoo-module */

import { orm } from "@web/core/orm";
import { registry } from "@web/core/registry";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { DashboardLoader, Status } from "./dashboard_loader";
import { Spreadsheet } from "@odoo/o-spreadsheet";
import { useSetupAction } from "@web/webclient/actions/action_hook";
import { DashboardMobileSearchPanel } from "./mobile_search_panel/mobile_search_panel";
import { MobileFigureContainer } from "./mobile_figure_container/mobile_figure_container";
import { FilterValue } from "@spreadsheet/global_filters/components/filter_value/filter_value";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { SpreadsheetShareButton } from "@spreadsheet/components/share_button/share_button";
import { useSpreadsheetPrint } from "@spreadsheet/hooks";

import { Component, onWillStart, useState, useEffect } from "@odoo/owl";

export class SpreadsheetDashboardAction extends Component {
    static template = "spreadsheet_dashboard.DashboardAction";
    static components = {
        ControlPanel,
        Spreadsheet,
        FilterValue,
        DashboardMobileSearchPanel,
        MobileFigureContainer,
        SpreadsheetShareButton,
    };
    static props = { ...standardActionServiceProps };

    setup() {
        this.Status = Status;
        this.controlPanelDisplay = {};
        this.router = useService("router");
        /** @type {DashboardLoader}*/
        this.loader = useState(new DashboardLoader(this.env));
        onWillStart(async () => {
            if (this.props.state && this.props.state.dashboardLoader) {
                const { groups, dashboards } = this.props.state.dashboardLoader;
                this.loader.restoreFromState(groups, dashboards);
            } else {
                await this.loader.load();
            }
            const activeDashboardId = this.getInitialActiveDashboard();
            if (activeDashboardId) {
                this.openDashboard(activeDashboardId);
            }
        });
        useEffect(
            () => this.router.pushState({ dashboard_id: this.activeDashboardId }),
            () => [this.activeDashboardId]
        );
        useEffect(
            () => {
                const dashboard = this.state.activeDashboard;
                if (dashboard && dashboard.status === Status.Loaded) {
                    const render = () => this.render(true);
                    dashboard.model.on("update", this, render);
                    return () => dashboard.model.off("update", this, render);
                }
            },
            () => {
                const dashboard = this.state.activeDashboard;
                return [dashboard?.model, dashboard?.status];
            }
        );
        useSetupAction({
            getLocalState: () => {
                return {
                    activeDashboardId: this.activeDashboardId,
                    dashboardLoader: this.loader.getState(),
                };
            },
        });
        useSpreadsheetPrint(() => this.state.activeDashboard?.model);
        /** @type {{ activeDashboard: import("./dashboard_loader").Dashboard}} */
        this.state = useState({ activeDashboard: undefined });
    }

    /**
     * @returns {number | undefined}
     */
    get activeDashboardId() {
        return this.state.activeDashboard ? this.state.activeDashboard.id : undefined;
    }

    /**
     * @returns {object[]}
     */
    get filters() {
        const dashboard = this.state.activeDashboard;
        if (!dashboard || dashboard.status !== Status.Loaded) {
            return [];
        }
        return dashboard.model.getters.getGlobalFilters();
    }

    /**
     * @private
     * @returns {number | undefined}
     */
    getInitialActiveDashboard() {
        if (this.props.state && this.props.state.activeDashboardId) {
            return this.props.state.activeDashboardId;
        }
        const params = this.props.action.params || this.props.action.context.params;
        if (params && params.dashboard_id) {
            return params.dashboard_id;
        }
        const [firstSection] = this.getDashboardGroups();
        if (firstSection && firstSection.dashboards.length) {
            return firstSection.dashboards[0].id;
        }
    }

    getDashboardGroups() {
        return this.loader.getDashboardGroups();
    }

    /**
     * @param {number} dashboardId
     */
    openDashboard(dashboardId) {
        this.state.activeDashboard = this.loader.getDashboard(dashboardId);
    }

    async shareSpreadsheet(data, excelExport) {
        const url = await orm.call("spreadsheet.dashboard.share", "action_get_share_url", [
            {
                dashboard_id: this.activeDashboardId,
                spreadsheet_data: JSON.stringify(data),
                excel_files: excelExport.files,
            },
        ]);
        return url;
    }
}

registry
    .category("actions")
    .add("action_spreadsheet_dashboard", SpreadsheetDashboardAction, { force: true });
