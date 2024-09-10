import { ImStatus } from "@mail/core/common/im_status";
import { NavigableList } from "@mail/core/common/navigable_list";
import { cleanTerm } from "@mail/utils/common/format";
import { useSequential } from "@mail/utils/common/hooks";

import { Component, useEffect, useRef, useState } from "@odoo/owl";

import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { TagsList } from "@web/core/tags_list/tags_list";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { isEventHandled } from "@web/core/utils/misc";

export class DiscussSearch extends Component {
    static template = "mail.DiscussSearch";
    static props = [
        "autofocus?",
        "category?",
        "onCompleted?",
        "groupChats?",
        "onSearchValueChanged?",
        "canCreate?",
    ];
    static defaultProps = { groupChats: true, canCreate: true };
    static components = { NavigableList, TagsList, ImStatus };

    setup() {
        super.setup();
        this.store = useState(useService("mail.store"));
        this.orm = useService("orm");
        this.sequential = useSequential();
        this.discussCoreCommonService = useState(useService("discuss.core.common"));
        this.state = useState({
            searchValue: "",
            selectedPartners: [],
            isFetching: false,
        });
        this.searchBoxRef = useRef("searchBox");
        this.searchInputRef = useRef("searchInput");
        if (this.props.autofocus) {
            useAutofocus({ refName: "searchInput" });
        }
        useEffect(
            () => {
                this.props.onSearchValueChanged?.(this.state.searchValue);
                this.fetchSuggestions();
            },
            () => [this.state.searchValue]
        );
    }

    get inputPlaceholder() {
        if (this.state.selectedPartners.length) {
            return _t("Press Enter to start the conversation");
        } else if (!this.props.category) {
            return _t("Search channels and DMs");
        } else {
            return this.props.category.addTitle;
        }
    }

    async fetchSuggestions() {
        const cleanedTerm = cleanTerm(this.state.searchValue);
        if (!cleanedTerm) {
            return;
        }
        const data = await this.sequential(async () => {
            this.state.isFetching = true;
            const data = await rpc("/discuss/search", {
                term: cleanedTerm,
                category_id: this.props.category?.id,
            });
            this.state.isFetching = false;
            return data;
        });
        this.store.insert(data);
    }

    get suggestions() {
        const cleanedTerm = cleanTerm(this.state.searchValue);
        const suggestions = [];
        if (!cleanedTerm) {
            return suggestions;
        }
        if (!this.props.category || this.props.category === this.store.discuss.chats) {
            suggestions.push(
                ...Object.values(this.store.Persona.records)
                    .filter(
                        (persona) =>
                            persona !== this.store.self &&
                            persona.isInternalUser &&
                            cleanTerm(persona.name).includes(cleanedTerm)
                    )
                    .map((persona) => {
                        return {
                            optionTemplate: "discuss.DiscussSearch.partner",
                            classList: "o-mail-DiscussSearch-suggestion",
                            partner: persona,
                            group: 10,
                        };
                    })
            );
            if (this.state.selectedPartners.length) {
                return suggestions;
            }
        }
        if (!this.props.category || this.props.category === this.store.discuss.channels) {
            suggestions.push(
                ...Object.values(this.store.Thread.records)
                    .filter(
                        (thread) =>
                            thread.channel_type === "channel" &&
                            cleanTerm(thread.name).includes(cleanedTerm)
                    )
                    .map((thread) => {
                        return {
                            optionTemplate: "discuss.DiscussSearch.channel",
                            classList: "o-mail-DiscussSearch-suggestion",
                            channel: thread,
                            group: 90,
                        };
                    })
            );
        }
        return suggestions;
    }

    get navigableListProps() {
        const props = {
            anchorRef: this.searchBoxRef?.el,
            position: "bottom-fit",
            onSelect: (ev, option) => this.onSelect(option),
            options: [],
            isLoading: this.state.isFetching,
            groupSeparators: false,
        };
        if (!this.state.searchValue) {
            return props;
        }
        props.options = this.suggestions.slice(0, 8);
        if (
            this.props.canCreate &&
            !this.state.selectedPartners.length &&
            (!this.props.category || this.props.category === this.store.discuss.channels)
        ) {
            props.options.push({
                createChannel: true,
                optionTemplate: "discuss.DiscussSearch.new",
                classList: "o-mail-DiscussSearch-suggestion",
                label: this.state.searchValue,
                group: 100,
            });
        }
        if (!props.options.length && !this.state.isFetching) {
            props.options.push({
                classList: "o-mail-DiscussSearch-suggestion",
                label: _t("No results found"),
                unselectable: true,
            });
        }
        return props;
    }

    async onSelect(option) {
        if (option.createChannel) {
            this.env.services.orm
                .call("discuss.channel", "channel_create", [
                    option.label,
                    this.store.internalUserGroupId,
                ])
                .then((data) => {
                    const { Thread } = this.store.insert(data);
                    const [channel] = Thread;
                    channel.open();
                });
        } else if (option.channel) {
            const channel = await this.store.Thread.getOrFetch(option.channel);
            channel.open();
        } else if (option.partner) {
            if (this.props.groupChats) {
                if (!this.state.selectedPartners.includes(option.partner.id)) {
                    this.state.selectedPartners.push(option.partner.id);
                }
            } else {
                this.discussCoreCommonService.startChat([option.partner.id]);
            }
        }
        this.state.searchValue = "";
        if (!this.props.groupChats) {
            this.props.onCompleted?.();
        }
    }

    get tagsList() {
        const res = [];
        for (const partnerId of this.state.selectedPartners) {
            const partner = this.store.Persona.get({ type: "partner", id: partnerId });
            res.push({
                id: partner.id,
                text: partner.name,
                className: "m-1 py-1",
                colorIndex: Math.floor(partner.name.length % 10),
                onDelete: () => this.removeFromSelectedPartners(partnerId),
            });
        }
        return res;
    }

    removeFromSelectedPartners(id) {
        this.state.selectedPartners = this.state.selectedPartners.filter(
            (partnerId) => partnerId !== id
        );
        this.searchInputRef.el.focus();
    }

    onKeydownInput(ev) {
        const hotkey = getActiveHotkey(ev);
        switch (hotkey) {
            case "enter":
                if (
                    isEventHandled(ev, "NavigableList.select") ||
                    !this.state.searchValue === "" ||
                    this.state.selectedPartners.length === 0
                ) {
                    return;
                }
                this.discussCoreCommonService.startChat(this.state.selectedPartners);
                this.state.selectedPartners = [];
                this.props.onCompleted?.();
                break;
            case "backspace":
                if (this.state.selectedPartners.length > 0 && this.state.searchValue === "") {
                    this.state.selectedPartners.pop();
                }
                return;
            default:
                return;
        }
        ev.stopPropagation();
        ev.preventDefault();
    }
}
