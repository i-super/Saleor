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
import {
  VoucherDiscountValueType,
  VoucherType
} from "../../../types/globalTypes";
import { translateVoucherTypes } from "../../translations";
import { VoucherDetails_voucher } from "../../types/VoucherDetails";

export interface VoucherSummaryProps {
  defaultCurrency: string;
  voucher: VoucherDetails_voucher;
}

const VoucherSummary: React.StatelessComponent<VoucherSummaryProps> = ({
  defaultCurrency,
  voucher
}) => {
  const translatedVoucherTypes = translateVoucherTypes();

  return (
    <Card>
      <CardTitle title={i18n.t("Summary")} />
      <CardContent>
        <Typography variant="body2">{i18n.t("Name")}</Typography>
        <Typography>
          {maybe<React.ReactNode>(() => voucher.name, <Skeleton />)}
        </Typography>
        <FormSpacer />

        <Typography variant="body2">{i18n.t("Applies to")}</Typography>
        <Typography>
          {maybe<React.ReactNode>(
            () => translatedVoucherTypes[voucher.type],
            <Skeleton />
          )}
        </Typography>
        <FormSpacer />

        <Typography variant="body2">{i18n.t("Value")}</Typography>
        <Typography>
          {maybe<React.ReactNode>(
            () =>
              voucher.discountValueType === VoucherDiscountValueType.FIXED ? (
                <Money
                  money={{
                    amount: voucher.discountValue,
                    currency: defaultCurrency
                  }}
                />
              ) : (
                <Percent amount={voucher.discountValue} />
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
              <DateFormatter date={voucher.startDate} />
            ),
            <Skeleton />
          )}
        </Typography>
        <FormSpacer />

        <Typography variant="body2">{i18n.t("End Date")}</Typography>
        <Typography>
          {maybe<React.ReactNode>(
            () =>
              voucher.endDate === null ? (
                "-"
              ) : (
                <DateFormatter date={voucher.endDate} />
              ),
            <Skeleton />
          )}
        </Typography>
      </CardContent>

      <Hr />

      <CardContent>
        <Typography variant="body2">{i18n.t("Min. Order Value")}</Typography>
        <Typography>
          {maybe<React.ReactNode>(
            () =>
              voucher.minAmountSpent ? (
                <Money money={voucher.minAmountSpent} />
              ) : (
                "-"
              ),
            <Skeleton />
          )}
        </Typography>
        <FormSpacer />

        <Typography variant="body2">{i18n.t("Usage Limit")}</Typography>
        <Typography>
          {maybe<React.ReactNode>(
            () => (voucher.usageLimit === null ? "-" : voucher.usageLimit),
            <Skeleton />
          )}
        </Typography>
      </CardContent>
    </Card>
  );
};
VoucherSummary.displayName = "VoucherSummary";
export default VoucherSummary;
