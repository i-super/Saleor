import Button from "@material-ui/core/Button";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Hidden from "@material-ui/core/Hidden";
import { withStyles } from "@material-ui/core/styles";
import Table from "@material-ui/core/Table";
import TableBody from "@material-ui/core/TableBody";
import TableCell from "@material-ui/core/TableCell";
import TableHead from "@material-ui/core/TableHead";
import TableRow from "@material-ui/core/TableRow";
import Typography from "@material-ui/core/Typography";
import * as React from "react";

import { MoneyType } from "../..";
import CardTitle from "../../../components/CardTitle";
import Money from "../../../components/Money";
import Skeleton from "../../../components/Skeleton";
import StatusLabel from "../../../components/StatusLabel";
import i18n from "../../../i18n";
import { renderCollection } from "../../../misc";

interface ProductVariantsProps {
  disabled?: boolean;
  variants?: Array<{
    id: string;
    sku: string;
    name: string;
    priceOverride?: MoneyType;
    stockQuantity: number;
    margin: number;
  }>;
  fallbackPrice?: MoneyType;
  onAttributesEdit: () => void;
  onRowClick: (id: string) => () => void;
  onVariantAdd?();
}

const decorate = withStyles(theme => {
  const dot = {
    borderRadius: "100%",
    display: "inline-block",
    height: theme.spacing.unit,
    marginRight: theme.spacing.unit,
    width: theme.spacing.unit
  };
  return {
    denseTable: {
      "& td, & th": {
        paddingRight: theme.spacing.unit * 3
      }
    },
    link: {
      cursor: "pointer"
    },
    textLeft: {
      textAlign: "left" as "left"
    },
    textRight: {
      textAlign: "right" as "right"
    }
  };
});

export const ProductVariants = decorate<ProductVariantsProps>(
  ({
    classes,
    variants,
    fallbackPrice,
    onAttributesEdit,
    onRowClick,
    onVariantAdd
  }) => (
    <Card>
      <CardTitle
        title={i18n.t("Variants")}
        toolbar={
          <>
            {/* TODO: enable after adding attribute section */}
            {/* <Button onClick={onAttributesEdit} variant="flat" color="secondary">
              {i18n.t("Edit attributes")}
            </Button> */}
            <Button onClick={onVariantAdd} variant="flat" color="secondary">
              {i18n.t("Add variant")}
            </Button>
          </>
        }
      />
      <CardContent>
        <Typography>
          {i18n.t(
            "Use variants for products that come in a variety of version for example different sizes or colors"
          )}
        </Typography>
      </CardContent>
      <Table className={classes.denseTable}>
        <TableHead>
          <TableRow>
            <TableCell className={classes.textLeft}>{i18n.t("Name")}</TableCell>
            <TableCell>{i18n.t("Status")}</TableCell>
            <TableCell>{i18n.t("SKU")}</TableCell>
            <Hidden smDown>
              <TableCell className={classes.textRight}>
                {i18n.t("Price")}
              </TableCell>
            </Hidden>
          </TableRow>
        </TableHead>
        <TableBody>
          {renderCollection(
            variants,
            variant => (
              <TableRow
                hover={!!variant}
                key={variant ? variant.id : "skeleton"}
              >
                <TableCell
                  className={[classes.textLeft, classes.link].join(" ")}
                  onClick={onRowClick(variant.id)}
                >
                  {variant ? variant.name || variant.sku : <Skeleton />}
                </TableCell>
                <TableCell>
                  {variant ? (
                    <StatusLabel
                      status={variant.stockQuantity > 0 ? "success" : "error"}
                      label={
                        variant.stockQuantity > 0
                          ? i18n.t("Available")
                          : i18n.t("Unavailable")
                      }
                    />
                  ) : (
                    <Skeleton />
                  )}
                </TableCell>
                <TableCell>{variant ? variant.sku : <Skeleton />}</TableCell>
                <Hidden smDown>
                  <TableCell className={classes.textRight}>
                    {variant ? (
                      variant.priceOverride ? (
                        <Money
                          amount={variant.priceOverride.amount}
                          currency={variant.priceOverride.currency}
                        />
                      ) : fallbackPrice ? (
                        <Money
                          amount={fallbackPrice.amount}
                          currency={fallbackPrice.currency}
                        />
                      ) : (
                        <Skeleton />
                      )
                    ) : (
                      <Skeleton />
                    )}
                  </TableCell>
                </Hidden>
              </TableRow>
            ),
            () => (
              <TableRow>
                <TableCell colSpan={2}>
                  {i18n.t("This product has no variants")}
                </TableCell>
              </TableRow>
            )
          )}
        </TableBody>
      </Table>
    </Card>
  )
);
ProductVariants.displayName = "ProductVariants";
export default ProductVariants;
