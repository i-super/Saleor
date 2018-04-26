import Card, { CardContent } from "material-ui/Card";
import blue from "material-ui/colors/blue";
import green from "material-ui/colors/green";
import red from "material-ui/colors/red";
import { FormControlLabel } from "material-ui/Form";
import Hidden from "material-ui/Hidden";
import { withStyles } from "material-ui/styles";
import Switch from "material-ui/Switch";
import Table, {
  TableBody,
  TableCell,
  TableHead,
  TableRow
} from "material-ui/Table";
import Typography from "material-ui/Typography";
import * as React from "react";

import PageHeader from "../../../components/PageHeader";
import Skeleton from "../../../components/Skeleton";
import i18n from "../../../i18n";

interface ProductVariantsProps {
  variants?: Array<{
    id: string;
    sku: string;
    name: string;
    priceOverride: {
      localized: string;
    };
    stockQuantity: number;
  }>;
  fallbackPrice?: string;
  fallbackGross?: string;
  onRowClick?(id: string);
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
    alignRightText: {
      textAlign: "right" as "right"
    },
    greenDot: {
      ...dot,
      backgroundColor: green[500]
    },
    link: {
      color: blue[500],
      cursor: "pointer"
    },
    redDot: {
      ...dot,
      backgroundColor: red[500]
    }
  };
});
export const ProductVariants = decorate<ProductVariantsProps>(
  ({ classes, variants, fallbackPrice, fallbackGross, onRowClick }) => (
    <Card>
      <PageHeader title={i18n.t("Variants")} />
      <Table>
        <TableHead>
          <TableRow>
            <Hidden smDown>
              <TableCell>{i18n.t("SKU")}</TableCell>
            </Hidden>
            <TableCell>{i18n.t("Name")}</TableCell>
            <TableCell>{i18n.t("Status")}</TableCell>
            <Hidden smDown>
              <TableCell className={classes.alignRightText}>
                {i18n.t("Price")}
              </TableCell>
              <TableCell className={classes.alignRightText}>
                {i18n.t("Gross margin")}
              </TableCell>
            </Hidden>
          </TableRow>
        </TableHead>
        <TableBody>
          {variants === undefined || variants === null ? (
            <TableRow>
              <Hidden smDown>
                <TableCell>
                  <Skeleton />
                </TableCell>
              </Hidden>
              <TableCell>
                <Skeleton />
              </TableCell>
              <TableCell>
                <Skeleton />
              </TableCell>
              <Hidden smDown>
                <TableCell className={classes.alignRightText}>
                  <Skeleton />
                </TableCell>
                <TableCell className={classes.alignRightText}>
                  <Skeleton />
                </TableCell>
              </Hidden>
            </TableRow>
          ) : variants.length > 0 ? (
            variants.map(variant => (
              <TableRow key={variant.id}>
                <Hidden smDown>
                  <TableCell>{variant.sku}</TableCell>
                </Hidden>
                <TableCell
                  className={onRowClick ? classes.link : ""}
                  onClick={onRowClick ? onRowClick(variant.id) : () => {}}
                >
                  {variant.name}
                </TableCell>
                <TableCell>
                  <span
                    className={
                      variant.stockQuantity > 0
                        ? classes.greenDot
                        : classes.redDot
                    }
                  />
                  {variant.stockQuantity > 0
                    ? i18n.t("Available")
                    : i18n.t("Unavailable")}
                </TableCell>
                <Hidden smDown>
                  <TableCell className={classes.alignRightText}>
                    {variant.priceOverride
                      ? variant.priceOverride.localized
                      : fallbackPrice}
                  </TableCell>
                  <TableCell className={classes.alignRightText}>
                    {/* TODO: replace with costPrice */}
                    {variant.priceOverride
                      ? variant.priceOverride.localized
                      : fallbackGross}
                  </TableCell>
                </Hidden>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={2}>
                {i18n.t("This product has no variants")}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </Card>
  )
);
ProductVariants.displayName = "ProductVariants";
export default ProductVariants;
