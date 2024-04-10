import { registry } from '@web/core/registry';
import { EditMenuDialog } from '@website/components/dialog/edit_menu';

class CustomEditMenuDialog extends EditMenuDialog {
    /*
     *  Overwrite addMenu method to handle event page URLs
     */

    addMenu(isMegaMenu, customUrl) {
        let eventPagePrefix = customUrl;
        const websiteMetadata = this.website.currentWebsite.metadata;
        if (websiteMetadata.mainObject?.model === "event.event") {
            const eventName = websiteMetadata.path.split('/event/')[1].split('/')[0];
            eventPagePrefix = `/event/${eventName}/page`;
        }
        super.addMenu(isMegaMenu, eventPagePrefix);
    }
}

registry.category('website_custom_menus').add('website.custom_menu_edit_menu', {
    Component: CustomEditMenuDialog,
    isDisplayed: (env) => env.services.website.currentWebsite
        && env.services.website.currentWebsite.metadata.contentMenus
        && env.services.website.currentWebsite.metadata.contentMenus.length,
}, { force: true });
