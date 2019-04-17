import Button from "@material-ui/core/Button";
import Card from "@material-ui/core/Card";
import Checkbox from "@material-ui/core/Checkbox";
import IconButton from "@material-ui/core/IconButton";
import { createStyles, withStyles, WithStyles } from "@material-ui/core/styles";
import Table from "@material-ui/core/Table";
import TableBody from "@material-ui/core/TableBody";
import TableCell from "@material-ui/core/TableCell";
import TableFooter from "@material-ui/core/TableFooter";
import TableRow from "@material-ui/core/TableRow";
import DeleteIcon from "@material-ui/icons/Delete";
import * as React from "react";

import CardTitle from "../../../components/CardTitle";
import Skeleton from "../../../components/Skeleton";
import TableHead from "../../../components/TableHead";
import TablePagination from "../../../components/TablePagination";
import useBulkActions from "../../../hooks/useBulkActions";
import i18n from "../../../i18n";
import { renderCollection } from "../../../misc";
import { ListActionProps, ListProps } from "../../../types";

const styles = createStyles({
  centerText: {
    textAlign: "center"
  },
  tableRow: {
    cursor: "pointer"
  },
  wideColumn: {
    width: "100%"
  }
});

interface CategoryListProps
  extends ListProps,
    ListActionProps<"onBulkDelete">,
    WithStyles<typeof styles> {
  categories?: Array<{
    id: string;
    name: string;
    children: {
      totalCount: number;
    };
    products: {
      totalCount: number;
    };
  }>;
  isRoot: boolean;
  onAdd?();
}

const CategoryList = withStyles(styles, { name: "CategoryList" })(
  ({
    categories,
    classes,
    disabled,
    isRoot,
    pageInfo,
    onAdd,
    onBulkDelete,
    onNextPage,
    onPreviousPage,
    onRowClick
  }: CategoryListProps) => {
    const { isMember: isChecked, listElements, toggle } = useBulkActions(
      categories
    );

    return (
      <Card>
        {!isRoot && (
          <CardTitle
            title={i18n.t("All Subcategories")}
            toolbar={
              <Button color="primary" variant="text" onClick={onAdd}>
                {i18n.t("Add subcategory")}
              </Button>
            }
          />
        )}
        <Table>
          <TableHead
            selected={listElements.length}
            toolbar={
              <IconButton
                color="primary"
                onClick={() => onBulkDelete(listElements)}
              >
                <DeleteIcon />
              </IconButton>
            }
          >
            <TableRow>
              <TableCell />
              <TableCell className={classes.wideColumn}>
                {i18n.t("Category Name", { context: "object" })}
              </TableCell>
              <TableCell className={classes.centerText}>
                {i18n.t("Subcategories", { context: "object" })}
              </TableCell>
              <TableCell className={classes.centerText}>
                {i18n
                  .t("No. Products", { context: "object" })
                  .replace(" ", "\xa0")}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableFooter>
            <TableRow>
              <TablePagination
                colSpan={4}
                hasNextPage={
                  pageInfo && !disabled ? pageInfo.hasNextPage : false
                }
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
              categories,
              category => {
                const isSelected = category ? isChecked(category.id) : false;

                return (
                  <TableRow
                    className={classes.tableRow}
                    hover={!!category}
                    onClick={category ? onRowClick(category.id) : undefined}
                    key={category ? category.id : "skeleton"}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        color="primary"
                        checked={isSelected}
                        disabled={disabled}
                        onClick={event => {
                          toggle(category.id);
                          event.stopPropagation();
                        }}
                      />
                    </TableCell>
                    <TableCell className={classes.wideColumn}>
                      {category && category.name ? category.name : <Skeleton />}
                    </TableCell>
                    <TableCell className={classes.centerText}>
                      {category &&
                      category.children &&
                      category.children.totalCount !== undefined ? (
                        category.children.totalCount
                      ) : (
                        <Skeleton />
                      )}
                    </TableCell>
                    <TableCell className={classes.centerText}>
                      {category &&
                      category.products &&
                      category.products.totalCount !== undefined ? (
                        category.products.totalCount
                      ) : (
                        <Skeleton />
                      )}
                    </TableCell>
                  </TableRow>
                );
              },
              () => (
                <TableRow>
                  <TableCell colSpan={4}>
                    {isRoot
                      ? i18n.t("No categories found")
                      : i18n.t("No subcategories found")}
                  </TableCell>
                </TableRow>
              )
            )}
          </TableBody>
        </Table>
      </Card>
    );
  }
);
CategoryList.displayName = "CategoryList";
export default CategoryList;
