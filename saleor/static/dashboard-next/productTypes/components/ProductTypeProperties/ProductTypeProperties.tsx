import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import * as React from "react";

import CardTitle from "../../../components/CardTitle";
import ControlledCheckbox from "../../../components/ControlledCheckbox";
import FormSpacer from "../../../components/FormSpacer";
import SingleSelectField from "../../../components/SingleSelectField";
import i18n from "../../../i18n";
import { translatedTaxRates as taxRates } from "../../../misc";

interface ProductTypePropertiesProps {
  data?: {
    isShippingRequired: boolean;
    hasVariants: boolean;
    taxRate: string;
  };
  disabled: boolean;
  onChange: (event: React.ChangeEvent<any>) => void;
}

const taxRateChoices = Object.keys(taxRates()).map(key => ({
  label: taxRates()[key],
  value: key
}));

const ProductTypeProperties: React.StatelessComponent<
  ProductTypePropertiesProps
> = ({ data, disabled, onChange }) => (
  <Card>
    <CardTitle title={i18n.t("Properties")} />
    <CardContent>
      <ControlledCheckbox
        checked={data.hasVariants}
        disabled={disabled}
        label={i18n.t("Has variants")}
        name="hasVariants"
        onChange={onChange}
      />
      <ControlledCheckbox
        checked={data.isShippingRequired}
        disabled={disabled}
        label={i18n.t("Requires shipping")}
        name="isShippingRequired"
        onChange={onChange}
      />
      <FormSpacer />
      <SingleSelectField
        choices={taxRateChoices}
        hint={i18n.t("Optional")}
        label={i18n.t("Tax rate")}
        name="taxRate"
        onChange={onChange}
        value={data.taxRate}
      />
    </CardContent>
  </Card>
);
ProductTypeProperties.displayName = "ProductTypeProperties";
export default ProductTypeProperties;
