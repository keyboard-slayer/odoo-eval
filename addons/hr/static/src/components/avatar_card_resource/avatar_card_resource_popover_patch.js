
import { patch } from "@web/core/utils/patch";
import { AvatarCardResourcePopover } from "@resource_mail/components/avatar_card_resource/avatar_card_resource_popover";
import { TagsList } from "@web/core/tags_list/tags_list";
import { HrPresenceStatus } from "@hr/components/hr_presence_status/hr_presence_status";


export const patchAvatarCardResourcePopover = {
    get fieldSpecification() {
        const fieldSpec = super.fieldSpecification;
        fieldSpec.employee_id = {
            fields: {
                ...fieldSpec.user_id.fields.employee_id.fields,
                show_hr_icon_display: {},
                hr_icon_display: {},
            },
        };
        delete fieldSpec.user_id.fields.employee_id;
        return fieldSpec;
    },

    get employee() {
        return super.employee?.[0];
    },
};

AvatarCardResourcePopover.components = {
    ...AvatarCardResourcePopover.components,
    TagsList,
};

AvatarCardResourcePopover.template = "hr.AvatarCardResourcePopover";
