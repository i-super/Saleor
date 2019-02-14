import Button from "@material-ui/core/Button";
import Card from "@material-ui/core/Card";
import { createStyles, withStyles, WithStyles } from "@material-ui/core/styles";
import Table from "@material-ui/core/Table";
import TableBody from "@material-ui/core/TableBody";
import TableCell from "@material-ui/core/TableCell";
import TableFooter from "@material-ui/core/TableFooter";
import TableHead from "@material-ui/core/TableHead";
import TableRow from "@material-ui/core/TableRow";
import * as React from "react";

import CardTitle from "../../../components/CardTitle";
import Skeleton from "../../../components/Skeleton";
import TablePagination from "../../../components/TablePagination";
import i18n from "../../../i18n";
import { maybe, renderCollection } from "../../../misc";
import { ListProps } from "../../../types";
import { SaleDetails_sale } from "../../types/SaleDetails";
import { VoucherDetails_voucher } from "../../types/VoucherDetails";

export interface DiscountCategoriesProps extends ListProps {
  discount: SaleDetails_sale | VoucherDetails_voucher;
  onCategoryAssign: () => void;
}

const styles = createStyles({
  tableRow: {
    cursor: "pointer"
  },
  textRight: {
    textAlign: "right"
  },
  wideColumn: {
    width: "60%"
  }
});
const DiscountCategories = withStyles(styles, {
  name: "DiscountCategories"
})(
  ({
    discount: sale,
    classes,
    disabled,
    pageInfo,
    onCategoryAssign,
    onRowClick,
    onPreviousPage,
    onNextPage
  }: DiscountCategoriesProps & WithStyles<typeof styles>) => (
    <Card>
      <CardTitle
        title={i18n.t("Categories assigned to {{ saleName }}", {
          saleName: maybe(() => sale.name)
        })}
        toolbar={
          <Button variant="flat" color="secondary" onClick={onCategoryAssign}>
            {i18n.t("Assign categories")}
          </Button>
        }
      />
      <Table>
        <TableHead>
          <TableRow>
            <TableCell className={classes.wideColumn}>
              {i18n.t("Category name")}
            </TableCell>
            <TableCell className={classes.textRight}>
              {i18n.t("Products")}
            </TableCell>
          </TableRow>
        </TableHead>
        <TableFooter>
          <TableRow>
            <TablePagination
              colSpan={5}
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
            maybe(() => sale.categories.edges.map(edge => edge.node)),
            category => (
              <TableRow
                hover={!!category}
                key={category ? category.id : "skeleton"}
                onClick={category && onRowClick(category.id)}
                className={classes.tableRow}
              >
                <TableCell>
                  {maybe<React.ReactNode>(() => category.name, <Skeleton />)}
                </TableCell>
                <TableCell className={classes.textRight}>
                  {maybe<React.ReactNode>(
                    () => category.products.totalCount,
                    <Skeleton />
                  )}
                </TableCell>
              </TableRow>
            ),
            () => (
              <TableRow>
                <TableCell colSpan={2}>
                  {i18n.t("No categories found")}
                </TableCell>
              </TableRow>
            )
          )}
        </TableBody>
      </Table>
    </Card>
  )
);
DiscountCategories.displayName = "DiscountCategories";
export default DiscountCategories;
