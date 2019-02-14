import { storiesOf } from "@storybook/react";
import * as React from "react";

import SaleDetailsPage, {
  SaleDetailsPageProps,
  SaleDetailsPageTab
} from "../../../discounts/components/SaleDetailsPage";
import { sale } from "../../../discounts/fixtures";
import Decorator from "../../Decorator";
import { formError } from "../../misc";

const props: SaleDetailsPageProps = {
  activeTab: SaleDetailsPageTab.categories,
  defaultCurrency: "USD",
  disabled: false,
  errors: [],
  onBack: () => undefined,
  onNextPage: () => undefined,
  onPreviousPage: () => undefined,
  onRemove: () => undefined,
  onRowClick: () => () => undefined,
  onSubmit: () => undefined,
  onTabClick: () => undefined,
  pageInfo: {
    hasNextPage: true,
    hasPreviousPage: false
  },
  sale
};

storiesOf("Views / Discounts / Sale details", module)
  .addDecorator(Decorator)
  .add("default", () => <SaleDetailsPage {...props} />)
  .add("loading", () => (
    <SaleDetailsPage {...props} sale={undefined} disabled={true} />
  ))
  .add("form errors", () => (
    <SaleDetailsPage
      {...props}
      errors={["name", "startDate", "endDate", "value"].map(formError)}
    />
  ))
  .add("collections", () => (
    <SaleDetailsPage {...props} activeTab={SaleDetailsPageTab.collections} />
  ))
  .add("products", () => (
    <SaleDetailsPage {...props} activeTab={SaleDetailsPageTab.products} />
  ));
