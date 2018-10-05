import Button from "@material-ui/core/Button";
import Card from "@material-ui/core/Card";
import CardActions from "@material-ui/core/CardActions";
import CardContent from "@material-ui/core/CardContent";
import { withStyles } from "@material-ui/core/styles";
import * as React from "react";

import { transformPaymentStatus } from "../..";
import CardTitle from "../../../components/CardTitle";
import { Hr } from "../../../components/Hr";
import Money from "../../../components/Money";
import Skeleton from "../../../components/Skeleton";
import StatusLabel from "../../../components/StatusLabel";
import i18n from "../../../i18n";
import { maybe } from "../../../misc";
import { OrderStatus, PaymentStatusEnum } from "../../../types/globalTypes";
import { OrderDetails_order } from "../../types/OrderDetails";

interface OrderPaymentProps {
  order: OrderDetails_order;
  onCapture: () => void;
  onMarkAsPaid: () => void;
  onRefund: () => void;
  onRelease: () => void;
}

const decorate = withStyles(theme => ({
  root: {
    ...theme.typography.body1,
    lineHeight: 1.9,
    width: "100%"
  },
  textRight: {
    textAlign: "right" as "right"
  },
  totalRow: {
    fontWeight: 600 as 600
  }
}));
const OrderPayment = decorate<OrderPaymentProps>(
  ({ classes, order, onCapture, onMarkAsPaid, onRefund, onRelease }) => {
    const canCapture = maybe(() => order.paymentStatus)
      ? order.paymentStatus === PaymentStatusEnum.PREAUTH &&
        order.status !== OrderStatus.CANCELED
      : false;
    const canRelease = maybe(() => order.paymentStatus)
      ? order.paymentStatus === PaymentStatusEnum.PREAUTH
      : false;
    const canRefund = maybe(() => order.paymentStatus)
      ? order.paymentStatus === PaymentStatusEnum.CONFIRMED &&
        order.status !== OrderStatus.CANCELED
      : false;
    const canMarkAsPaid =
      maybe(() => order.paymentStatus) !== undefined
        ? [null, PaymentStatusEnum.ERROR, PaymentStatusEnum.REJECTED].includes(
            order.paymentStatus
          )
        : false;
    const payment = transformPaymentStatus(maybe(() => order.paymentStatus));
    return (
      <Card>
        <CardTitle
          title={
            maybe(() => order.paymentStatus) === undefined ? (
              <Skeleton />
            ) : (
              <StatusLabel label={payment.localized} status={payment.status} />
            )
          }
        />
        <CardContent>
          <table className={classes.root}>
            <tbody>
              <tr>
                <td>{i18n.t("Subtotal")}</td>
                <td>
                  {maybe(() => order.lines) === undefined ? (
                    <Skeleton />
                  ) : (
                    i18n.t("{{ quantity }} items", {
                      quantity: order.lines
                        .map(line => line.quantity)
                        .reduce((curr, prev) => prev + curr, 0)
                    })
                  )}
                </td>
                <td className={classes.textRight}>
                  {maybe(() => order.subtotal.gross) === undefined ? (
                    <Skeleton />
                  ) : (
                    <Money {...order.subtotal.gross} />
                  )}
                </td>
              </tr>
              <tr>
                <td>{i18n.t("Taxes")}</td>
                <td>
                  {maybe(() => order.total.tax) === undefined ? (
                    <Skeleton />
                  ) : order.total.tax.amount > 0 ? (
                    i18n.t("VAT included")
                  ) : (
                    i18n.t("does not apply")
                  )}
                </td>
                <td className={classes.textRight}>
                  {maybe(() => order.total.tax) === undefined ? (
                    <Skeleton />
                  ) : (
                    <Money {...order.total.tax} />
                  )}
                </td>
              </tr>
              <tr>
                <td>{i18n.t("Shipping")}</td>
                <td>
                  {maybe(() => order.shippingMethodName) === undefined &&
                  maybe(() => order.shippingPrice) === undefined ? (
                    <Skeleton />
                  ) : order.shippingMethodName === null ? (
                    i18n.t("does not apply")
                  ) : (
                    order.shippingMethodName
                  )}
                </td>
                <td className={classes.textRight}>
                  {maybe(() => order.shippingPrice.gross) === undefined ? (
                    <Skeleton />
                  ) : (
                    <Money {...order.shippingPrice.gross} />
                  )}
                </td>
              </tr>
              <tr className={classes.totalRow}>
                <td>{i18n.t("Total")}</td>
                <td />
                <td className={classes.textRight}>
                  {maybe(() => order.total.gross) === undefined ? (
                    <Skeleton />
                  ) : (
                    <Money {...order.total.gross} />
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </CardContent>
        {maybe(() => order.status) !== OrderStatus.CANCELED &&
          (canCapture || canRefund || canRelease || canMarkAsPaid) && (
            <>
              <Hr />
              <CardActions>
                {canCapture && (
                  <Button color="secondary" variant="flat" onClick={onCapture}>
                    {i18n.t("Capture", { context: "button" })}
                  </Button>
                )}
                {canRefund && (
                  <Button color="secondary" variant="flat" onClick={onRefund}>
                    {i18n.t("Refund", { context: "button" })}
                  </Button>
                )}
                {canRelease && (
                  <Button color="secondary" variant="flat" onClick={onRelease}>
                    {i18n.t("Release", { context: "button" })}
                  </Button>
                )}
                {canMarkAsPaid && (
                  <Button
                    color="secondary"
                    variant="flat"
                    onClick={onMarkAsPaid}
                  >
                    {i18n.t("Mark as paid", { context: "button" })}
                  </Button>
                )}
              </CardActions>
            </>
          )}
      </Card>
    );
  }
);
OrderPayment.displayName = "OrderPayment";
export default OrderPayment;
