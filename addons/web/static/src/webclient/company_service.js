import { browser } from "@web/core/browser/browser";
import { rpcBus } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { UPDATE_METHODS } from "@web/core/orm_service";
import { cookie } from "@web/core/browser/cookie";
import { user } from "@web/core/user";
import { router } from "@web/core/browser/router";

const CIDS_SEARCH_SEPARATOR = "-";

function parseCompanyIds(cids, separator = ",") {
    if (typeof cids === "string") {
        return cids.split(separator).map(Number);
    } else if (typeof cids === "number") {
        return [cids];
    }
    return [];
}

function formatCompanyIds(cids, separator = ",") {
    return cids.join(separator);
}

function computeActiveCompanyIds(cids) {
    const { user_companies } = session;
    let activeCompanyIds = cids || [];
    const availableCompaniesFromSession = user_companies.allowed_companies;
    const notAllowedCompanies = activeCompanyIds.filter(
        (id) => !(id in availableCompaniesFromSession)
    );

    if (!activeCompanyIds.length || notAllowedCompanies.length) {
        activeCompanyIds = [user_companies.current_company];
    }
    return activeCompanyIds;
}

function getCompanyIdsFromBrowser(state) {
    let cids;
    if ("cids" in state) {
        // backward compatibility s.t. old urls (still using "," as separator) keep working
        // deprecated as of 17.0
        let separator = CIDS_SEARCH_SEPARATOR;
        if (typeof state.cids === "string" && !state.cids.includes(CIDS_SEARCH_SEPARATOR)) {
            separator = ",";
        }
        cids = parseCompanyIds(state.cids, separator);
    } else if (cookie.get("cids")) {
        cids = parseCompanyIds(cookie.get("cids"));
    }
    return cids || [];
}

const errorHandlerRegistry = registry.category("error_handlers");
function accessErrorHandler(env, error, originalError) {
    const { _company_switching, resId } = router.current;
    if (
        !_company_switching ||
        originalError?.exceptionName !== "odoo.exceptions.AccessError" ||
        !resId
    ) {
        return false;
    }
    error.event?.preventDefault();
    // FIXME the action service will take care of restoring the previous valid controller, but because
    // the loadState crashed, the loadRouterState from webclient will not be able to set the menu.
    // Instead, we reload the page. This replaceState will race with the pushState of the actionService
    // restoring the previous valid controller, ideally we should find a way to just keep the loadRouterState
    // going after the loadState "failure" (ie it should communicate that it was able to load an action,
    // just not the orignally targetted one)
    router.replaceState(
        { resId: undefined, actionStack: router.current.actionStack.slice(0, -1) },
        { reload: true }
    );
    return true;
}

export const companyService = {
    dependencies: ["action"],
    start(env, { action }) {
        // Push an error handler in the registry. It needs to be before "rpcErrorHandler", which
        // has a sequence of 97. The default sequence of registry is 50.
        errorHandlerRegistry.add("accessErrorHandlerCompanies", accessErrorHandler);

        const allowedCompanies = session.user_companies.allowed_companies;
        const disallowedAncestorCompanies = session.user_companies.disallowed_ancestor_companies;
        const allowedCompaniesWithAncestors = {
            ...allowedCompanies,
            ...disallowedAncestorCompanies,
        };
        const activeCompanyIds = computeActiveCompanyIds(getCompanyIdsFromBrowser(router.current));

        // update browser data
        const cidsSearch = formatCompanyIds(activeCompanyIds, CIDS_SEARCH_SEPARATOR);
        router.addLockedKey("cids");
        router.replaceState({ cids: cidsSearch });
        cookie.set("cids", formatCompanyIds(activeCompanyIds));
        user.updateContext({ allowed_company_ids: activeCompanyIds });

        // reload the page if changes are being done to `res.company`
        rpcBus.addEventListener("RPC:RESPONSE", (ev) => {
            const { data, error } = ev.detail;
            const { model, method } = data.params;
            if (!error && model === "res.company" && UPDATE_METHODS.includes(method)) {
                if (!browser.localStorage.getItem("running_tour")) {
                    action.doAction("reload_context");
                }
            }
        });

        return {
            allowedCompanies,
            allowedCompaniesWithAncestors,
            disallowedAncestorCompanies,

            get activeCompanyIds() {
                return activeCompanyIds.slice();
            },

            get currentCompany() {
                return allowedCompanies[activeCompanyIds[0]];
            },

            getCompany(companyId) {
                return allowedCompaniesWithAncestors[companyId];
            },

            /**
             * @param {Array<>} companyIds - List of companies to log into
             * @param {boolean} [includeChildCompanies=true] - If true, will also
             * log into each child of each companyIds (default is true)
             */
            setCompanies(companyIds, includeChildCompanies = true) {
                const newCompanyIds = companyIds.length ? companyIds : [activeCompanyIds[0]];

                function addCompanies(companyIds) {
                    for (const companyId of companyIds) {
                        if (!newCompanyIds.includes(companyId)) {
                            newCompanyIds.push(companyId);
                            addCompanies(allowedCompanies[companyId].child_ids);
                        }
                    }
                }

                if (includeChildCompanies) {
                    addCompanies(
                        companyIds.flatMap((companyId) => allowedCompanies[companyId].child_ids)
                    );
                }

                const cidsSearch = formatCompanyIds(newCompanyIds, CIDS_SEARCH_SEPARATOR);
                cookie.set("cids", formatCompanyIds(newCompanyIds));
                router.pushState({ cids: cidsSearch, _company_switching: true }, { reload: true });
            },
        };
    },
};

registry.category("services").add("company", companyService);
