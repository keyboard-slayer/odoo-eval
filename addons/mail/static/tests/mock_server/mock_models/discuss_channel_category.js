import { fields, getKwArgs, makeKwArgs, models } from "@web/../tests/web_test_helpers";
import { DiscussChannel } from "./discuss_channel";
import { mailDataHelpers } from "../mail_mock_server";

export class DiscussChannelCategory extends models.ServerModel {
    _name = "discuss.channel.category";

    name = fields.Char({ string: "Channel category name", required: true });
    channel_ids = fields.One2many({
        relation: "discuss.channel",
        relation_field: "channel_category_id",
        string: "Channels",
    });

    get_categories() {
        return new mailDataHelpers.Store(this.browse()).get_result();
    }

    /** @param {number[]} ids */
    _to_store(ids, store) {
        const kwargs = getKwArgs(arguments, "ids", "store", "fields", "extra_fields");
        ids = kwargs.ids;

        const fields = {
            name: true,
        };

        const categories = this.browse(ids);
        for (const category of categories) {
            const channels = DiscussChannel.browse(category.channel_ids);
            store.add(channels.map((channel) => channel.id));
            const [data] = this.read(category.id, Object.keys(fields), makeKwArgs({ load: false }));
            store.add(this.browse(category.id), data);
        }
    }
}
