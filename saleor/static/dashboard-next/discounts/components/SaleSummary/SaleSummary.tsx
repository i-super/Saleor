import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Typography from "@material-ui/core/Typography";
import * as React from "react";

import CardTitle from "../../../components/CardTitle";
import DateFormatter from "../../../components/DateFormatter";
import FormSpacer from "../../../components/FormSpacer";
import Hr from "../../../components/Hr";
import Money from "../../../components/Money";
import Percent from "../../../components/Percent";
import Skeleton from "../../../components/Skeleton";
import i18n from "../../../i18n";
import { maybe } from "../../../misc";
import { SaleType } from "../../../types/globalTypes";
import { SaleDetails_sale } from "../../types/SaleDetails";

export interface SaleSummaryProps {
  defaultCurrency: string;
  sale: SaleDetails_sale;
}

const SaleSummary: React.StatelessComponent<SaleSummaryProps> = ({
  defaultCurrency,
  sale
}) => (
  <Card>
    <CardTitle title={i18n.t("Summary")} />
    <CardContent>
      <Typography variant="body2">{i18n.t("Name")}</Typography>
      <Typography>
        {maybe<React.ReactNode>(() => sale.name, <Skeleton />)}
      </Typography>
      <FormSpacer />

      <Typography variant="body2">{i18n.t("Value")}</Typography>
      <Typography>
        {maybe<React.ReactNode>(
          () =>
            sale.type === SaleType.FIXED ? (
              <Money
                money={{
                  amount: sale.value,
                  currency: defaultCurrency
                }}
              />
            ) : (
              <Percent amount={sale.value} />
            ),
          <Skeleton />
        )}
      </Typography>
    </CardContent>

    <Hr />

    <CardContent>
      <Typography variant="body2">{i18n.t("Start Date")}</Typography>
      <Typography>
        {maybe<React.ReactNode>(
          () => (
            <DateFormatter date={sale.startDate} />
          ),
          <Skeleton />
        )}
      </Typography>
      <FormSpacer />

      <Typography variant="body2">{i18n.t("End Date")}</Typography>
      <Typography>
        {maybe<React.ReactNode>(
          () =>
            sale.endDate === null ? "-" : <DateFormatter date={sale.endDate} />,
          <Skeleton />
        )}
      </Typography>
    </CardContent>
  </Card>
);
SaleSummary.displayName = "SaleSummary";
export default SaleSummary;
