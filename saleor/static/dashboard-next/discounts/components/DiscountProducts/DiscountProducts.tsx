import Button from "@material-ui/core/Button";
import Card from "@material-ui/core/Card";
import IconButton from "@material-ui/core/IconButton";
import {
  createStyles,
  Theme,
  withStyles,
  WithStyles
} from "@material-ui/core/styles";
import Table from "@material-ui/core/Table";
import TableBody from "@material-ui/core/TableBody";
import TableCell from "@material-ui/core/TableCell";
import TableFooter from "@material-ui/core/TableFooter";
import TableHead from "@material-ui/core/TableHead";
import TableRow from "@material-ui/core/TableRow";
import DeleteIcon from "@material-ui/icons/Delete";
import * as React from "react";

import CardTitle from "../../../components/CardTitle";
import Skeleton from "../../../components/Skeleton";
import StatusLabel from "../../../components/StatusLabel";
import TableCellAvatar from "../../../components/TableCellAvatar";
import TablePagination from "../../../components/TablePagination";
import i18n from "../../../i18n";
import { maybe, renderCollection } from "../../../misc";
import { ListProps } from "../../../types";
import { SaleDetails_sale } from "../../types/SaleDetails";
import { VoucherDetails_voucher } from "../../types/VoucherDetails";

export interface SaleProductsProps extends ListProps {
  discount: SaleDetails_sale | VoucherDetails_voucher;
  onProductAssign: () => void;
  onProductUnassign: (id: string) => void;
}

const styles = (theme: Theme) =>
  createStyles({
    iconCell: {
      "&:last-child": {
        paddingRight: 0
      },
      width: 48 + theme.spacing.unit / 2
    },
    tableRow: {
      cursor: "pointer"
    },
    textRight: {
      textAlign: "right"
    },
    wideColumn: {
      width: "40%"
    }
  });
const DiscountProducts = withStyles(styles, {
  name: "DiscountProducts"
})(
  ({
    discount: sale,
    classes,
    disabled,
    pageInfo,
    onRowClick,
    onPreviousPage,
    onProductAssign,
    onProductUnassign,
    onNextPage
  }: SaleProductsProps & WithStyles<typeof styles>) => (
    <Card>
      <CardTitle
        title={i18n.t("Products assigned to {{ saleName }}", {
          saleName: maybe(() => sale.name)
        })}
        toolbar={
          <Button variant="flat" color="secondary" onClick={onProductAssign}>
            {i18n.t("Assign products")}
          </Button>
        }
      />
      <Table>
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell className={classes.wideColumn}>
              {i18n.t("Product name")}
            </TableCell>
            <TableCell className={classes.textRight}>
              {i18n.t("Product Type")}
            </TableCell>
            <TableCell className={classes.textRight}>
              {i18n.t("Published")}
            </TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableFooter>
          <TableRow>
            <TablePagination
              colSpan={4}
              hasNextPage={pageInfo && !disabled ? pageInfo.hasNextPage : false}
              onNextPage={onNextPage}
              hasPreviousPage={
                pageInfo && !disabled ? pageInfo.hasPreviousPage : false
              }
              onPreviousPage={onPreviousPage}
            />
          </TableRow>
        </TableFooter>
        <TableBody>
          {renderCollection(
            maybe(() => sale.products.edges.map(edge => edge.node)),
            product => (
              <TableRow
                hover={!!product}
                key={product ? product.id : "skeleton"}
                onClick={product && onRowClick(product.id)}
                className={classes.tableRow}
              >
                <TableCellAvatar
                  thumbnail={maybe(() => product.thumbnail.url)}
                />
                <TableCell>
                  {maybe<React.ReactNode>(() => product.name, <Skeleton />)}
                </TableCell>
                <TableCell className={classes.textRight}>
                  {maybe<React.ReactNode>(
                    () => product.productType.name,
                    <Skeleton />
                  )}
                </TableCell>
                <TableCell className={classes.textRight}>
                  {product && product.isPublished !== undefined ? (
                    <StatusLabel
                      label={
                        product.isPublished
                          ? i18n.t("Published", { context: "product status" })
                          : i18n.t("Not published", {
                              context: "product status"
                            })
                      }
                      status={product.isPublished ? "success" : "error"}
                    />
                  ) : (
                    <Skeleton />
                  )}
                </TableCell>
                <TableCell className={classes.iconCell}>
                  <IconButton
                    disabled={!product || disabled}
                    onClick={event => {
                      event.stopPropagation();
                      onProductUnassign(product.id);
                    }}
                  >
                    <DeleteIcon color="secondary" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ),
            () => (
              <TableRow>
                <TableCell colSpan={4}>{i18n.t("No products found")}</TableCell>
              </TableRow>
            )
          )}
        </TableBody>
      </Table>
    </Card>
  )
);
DiscountProducts.displayName = "DiscountProducts";
export default DiscountProducts;
