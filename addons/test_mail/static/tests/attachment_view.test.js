import { defineTestMailModels } from "@test_mail/../tests/test_mail_test_helpers";
import { describe, test, expect } from "@odoo/hoot";
import { queryOne, waitUntil, click as hootClick } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    click,
    contains,
    openFormView,
    registerArchs,
    start,
    startServer,
    patchUiSize,
    SIZES,
} from "@mail/../tests/mail_test_helpers";
import { browser } from "@web/core/browser/browser";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineTestMailModels();

/*
 * This test makes sure that the attachment view controls are working in the following cases:
 * - Before opening the popout window
 * - Inside the popout window
 * - After closing the popout window
 */
test("Attachment view test", async () => {
    const popoutIframe = document.createElement("iframe");
    const popoutWindow = {
        closed: false,
        get document() {
            const doc = popoutIframe.contentDocument;
            const originalWrite = doc.write;
            doc.write = (content) => {
                // This avoids duplicating the test script in the popoutWindow
                const sanitizedContent = content.replace(
                    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
                    ""
                );
                originalWrite.call(doc, sanitizedContent);
            };
            return doc;
        },
        get body() {
            return popoutWindow.document.querySelector(".o_popout_wrapper");
        },
        close: () => {
            popoutWindow.closed = true;
            popoutIframe.remove(popoutWindow.body);
        },
        contains: async (selector) => {
            await animationFrame();
            await waitUntil(() => popoutWindow.body);
            const target = popoutWindow.body.querySelector(selector);
            expect(target).toBeDisplayed();
            return target;
        },
        click: async (selector) => {
            const target = await popoutWindow.contains(selector);
            hootClick(target);
        },
    };
    patchWithCleanup(browser, {
        open: () => {
            queryOne(".o_popout_holder").append(popoutIframe);
            return popoutWindow;
        },
    });

    const pyEnv = await startServer();
    const recordId = pyEnv["mail.test.simple.main.attachment"].create({
        display_name: "first partner",
        message_attachment_count: 2,
    });
    const attachmentIds = pyEnv["ir.attachment"].create([
        {
            mimetype: "image/jpeg",
            res_id: recordId,
            res_model: "mail.test.simple.main.attachment",
        },
        {
            mimetype: "application/pdf",
            res_id: recordId,
            res_model: "mail.test.simple.main.attachment",
        },
    ]);
    pyEnv["mail.message"].create({
        attachment_ids: attachmentIds,
        model: "mail.test.simple.main.attachment",
        res_id: recordId,
    });
    registerArchs({
        "mail.test.simple.main.attachment,false,form": `
                <form string="Test document">
                    <div class="o_popout_holder"/>
                    <sheet>
                        <field name="name"/>
                    </sheet>
                    <div class="o_attachment_preview"/>
                    <chatter/>
                </form>`,
    });

    patchUiSize({ size: SIZES.XXL });
    await start();
    await openFormView("mail.test.simple.main.attachment", recordId);
    await click(".o_attachment_preview .o_move_next");
    await contains(".o_attachment_preview img");
    await click(".o_attachment_preview .o_move_previous");
    await contains(".o_attachment_preview iframe");

    await click(".o_attachment_preview .o_attachment_control");

    await waitUntil(() => popoutWindow.body);
    expect(".o_attachment_preview").not.toBeVisible();

    await popoutWindow.click(".o_move_next");
    await popoutWindow.contains("img");
    await popoutWindow.click(".o_move_previous");
    await popoutWindow.contains("iframe");

    popoutWindow.close();
    await waitUntil(() => document.querySelector(".o_attachment_preview:not(.d-none)"), {
        timeout: 1500,
    });
    expect(".o_attachment_preview").toBeVisible();

    await click(".o_attachment_preview .o_move_next");
    await contains(".o_attachment_preview img");
    await click(".o_attachment_preview .o_move_previous");
    await contains(".o_attachment_preview iframe");

    await click(".o_attachment_preview .o_attachment_control");

    await waitUntil(() => popoutWindow.body);
    expect(".o_attachment_preview").not.toBeVisible();
});
