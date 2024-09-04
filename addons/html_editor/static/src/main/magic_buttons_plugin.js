import { Plugin } from "@html_editor/plugin";
import { closestBlock } from "@html_editor/utils/blocks";
import { isEmptyBlock } from "@html_editor/utils/dom_info";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { _t } from "@web/core/l10n/translation";

export class MagicButtonsPlugin extends Plugin {
    static name = "magic_buttons";
    static dependencies = ["selection", "local-overlay", "powerbox"];
    /** @type { (p: MagicButtonsPlugin) => Record<string, any> } */
    static resources = (p) => ({
        layoutGeometryChange: p.updateMagicButtons.bind(p),
        onSelectionChange: p.updateMagicButtons.bind(p),
        magicButtons: [
            {
                id: "more_options",
                title: _t("More options"),
                fontawesome: "fa-ellipsis-v",
                action: () => {
                    p.openPowerbox();
                },
                sequence: 7,
            },
        ],
    });

    setup() {
        this.buttons = this.resources.magicButtons.sort((a, b) => a.sequence - b.sequence);
        this.magicButtonsOverlay = this.shared.makeLocalOverlay("oe-magic-buttons-overlay");
        this.categories = this.resources.powerboxCategory.sort((a, b) => a.sequence - b.sequence);
        this.commands = this.resources.powerboxItems.map((command) => ({
            ...command,
            categoryName: this.categories.find((category) => category.id === command.category).name,
        }));
        this.createMagicButtons();
    }

    createMagicButtons() {
        this.magicButtons = document.createElement("div");
        this.magicButtons.className = `o_we_magic_buttons d-flex justify-content-center d-none`;
        for (const button of this.buttons) {
            const btn = document.createElement("div");
            btn.className = `magic_button btn px-2 py-1 cursor-pointer fa ${button.fontawesome}`;
            btn.addEventListener("click", () => this.applyCommand(button));
            this.magicButtons.appendChild(btn);
        }
        this.magicButtonsOverlay.appendChild(this.magicButtons);
    }

    updateMagicButtons() {
        this.magicButtons.classList.add("d-none");
        const { editableSelection, documentSelectionIsInEditable } = this.shared.getSelectionData();
        if (!documentSelectionIsInEditable) {
            return;
        }
        const block = closestBlock(editableSelection.anchorNode);
        const element = closestElement(editableSelection.anchorNode);
        if (
            editableSelection.isCollapsed &&
            element?.tagName === "P" &&
            isEmptyBlock(block) &&
            !this.services.ui.isSmall &&
            !closestElement(editableSelection.anchorNode, "td") &&
            !block.style.textAlign &&
            this.resources.showMagicButtons.every((showMagicButtons) =>
                showMagicButtons(editableSelection)
            )
        ) {
            this.magicButtons.classList.remove("d-none");
            let direction = block.getAttribute("dir");
            if (block.tagName === "LI") {
                direction = block.parentElement.getAttribute("dir");
            }
            this.magicButtons.setAttribute("dir", direction);
            this.setMagicButtonsPosition(block, direction);
        }
    }

    /**
     *
     * @param {HTMLElement} block
     * @param {string} direction
     */
    setMagicButtonsPosition(block, direction) {
        const overlayStyles = this.magicButtonsOverlay.style;
        // Resetting the position of the magic buttons.
        overlayStyles.top = "0px";
        overlayStyles.left = "0px";
        const blockRect = block.getBoundingClientRect();
        const buttonsRect = this.magicButtons.getBoundingClientRect();
        if (direction === "rtl") {
            overlayStyles.left =
                blockRect.right -
                buttonsRect.width -
                buttonsRect.x -
                buttonsRect.width * 0.85 +
                "px";
        } else {
            overlayStyles.left = blockRect.left - buttonsRect.x + buttonsRect.width * 0.85 + "px";
        }
        overlayStyles.top = blockRect.top - buttonsRect.top + "px";
        overlayStyles.height = blockRect.height + "px";
    }

    async applyCommand(command) {
        const btns = [...this.magicButtons.querySelectorAll(".btn")];
        btns.forEach((btn) => btn.classList.add("disabled"));
        await command.action(this.dispatch);
        btns.forEach((btn) => btn.classList.remove("disabled"));
    }

    openPowerbox() {
        const selection = this.shared.getEditableSelection();
        this.enabledCommands = this.commands.filter(
            (cmd) => !cmd.isAvailable?.(selection.anchorNode)
        );
        this.shared.openPowerbox({
            commands: this.enabledCommands,
            categories: this.categories,
        });
    }
}
