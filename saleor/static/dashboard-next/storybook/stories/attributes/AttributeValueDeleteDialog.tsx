import { storiesOf } from "@storybook/react";
import * as React from "react";

import AttributeValueDeleteDialog, {
  AttributeValueDeleteDialogProps
} from "../../../attributes/components/AttributeValueDeleteDialog";
import Decorator from "../../Decorator";

const props: AttributeValueDeleteDialogProps = {
  confirmButtonState: "default",
  name: "XS",
  onClose: () => undefined,
  onConfirm: () => undefined,
  open: true
};

storiesOf("Attributes / Attribute value delete", module)
  .addDecorator(Decorator)
  .add("default", () => <AttributeValueDeleteDialog {...props} />);
