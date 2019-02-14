import { SaleType, VoucherDiscountValueType } from "../types/globalTypes";
import { SaleDetails_sale } from "./types/SaleDetails";
import { SaleList_sales_edges_node } from "./types/SaleList";
import { VoucherList_vouchers_edges_node } from "./types/VoucherList";

export const saleList: SaleList_sales_edges_node[] = [
  {
    __typename: "Sale" as "Sale",
    endDate: null,
    id: "U2FsZTo0",
    name: "Happy front day!",
    startDate: "2019-01-03",
    type: "PERCENTAGE" as SaleType,
    value: 40
  },
  {
    __typename: "Sale" as "Sale",
    endDate: null,
    id: "U2FsZTo1",
    name: "Happy minute day!",
    startDate: "2019-01-03",
    type: "FIXED" as SaleType,
    value: 30
  },
  {
    __typename: "Sale" as "Sale",
    endDate: null,
    id: "U2FsZTox",
    name: "Happy class day!",
    startDate: "2019-01-03",
    type: "PERCENTAGE" as SaleType,
    value: 10
  },
  {
    __typename: "Sale" as "Sale",
    endDate: null,
    id: "U2FsZToy",
    name: "Happy human day!",
    startDate: "2019-01-03",
    type: "PERCENTAGE" as SaleType,
    value: 20
  },
  {
    __typename: "Sale" as "Sale",
    endDate: null,
    id: "U2FsZToz",
    name: "Happy year day!",
    startDate: "2019-01-03",
    type: "PERCENTAGE" as SaleType,
    value: 10
  }
];

export const voucherList: VoucherList_vouchers_edges_node[] = [
  {
    __typename: "Voucher" as "Voucher",
    discountValue: 100,
    discountValueType: "PERCENTAGE" as VoucherDiscountValueType,
    endDate: null,
    id: "Vm91Y2hlcjox",
    minAmountSpent: null,
    name: "Free shipping",
    startDate: "2019-01-03",
    usageLimit: null
  },
  {
    __typename: "Voucher" as "Voucher",
    discountValue: 25,
    discountValueType: "FIXED" as VoucherDiscountValueType,
    endDate: null,
    id: "Vm91Y2hlcjoy",
    minAmountSpent: {
      __typename: "Money" as "Money",
      amount: 200,
      currency: "USD"
    },
    name: "Big order discount",
    startDate: "2019-01-03",
    usageLimit: 150
  }
];

export const sale: SaleDetails_sale = {
  __typename: "Sale",
  categories: {
    __typename: "CategoryCountableConnection",
    edges: [],
    pageInfo: {
      __typename: "PageInfo",
      endCursor: null,
      hasNextPage: false,
      hasPreviousPage: false,
      startCursor: null
    }
  },
  collections: {
    __typename: "CollectionCountableConnection",
    edges: [],
    pageInfo: {
      __typename: "PageInfo",
      endCursor: null,
      hasNextPage: false,
      hasPreviousPage: false,
      startCursor: null
    }
  },
  endDate: null,
  id: "U2FsZTo1",
  name: "Happy minute day!",
  products: {
    __typename: "ProductCountableConnection",
    edges: [
      {
        __typename: "ProductCountableEdge",
        node: {
          __typename: "Product",
          id: "UHJvZHVjdDo3MQ==",
          isPublished: true,
          name: "Orange Juice",
          productType: {
            __typename: "ProductType",
            id: "UHJvZHVjdFR5cGU6OQ==",
            name: "Juice"
          }
        }
      },
      {
        __typename: "ProductCountableEdge",
        node: {
          __typename: "Product",
          id: "UHJvZHVjdDo3Mw==",
          isPublished: true,
          name: "Carrot Juice",
          productType: {
            __typename: "ProductType",
            id: "UHJvZHVjdFR5cGU6OQ==",
            name: "Juice"
          }
        }
      },
      {
        __typename: "ProductCountableEdge",
        node: {
          __typename: "Product",
          id: "UHJvZHVjdDo3OQ==",
          isPublished: true,
          name: "Bean Juice",
          productType: {
            __typename: "ProductType",
            id: "UHJvZHVjdFR5cGU6OQ==",
            name: "Juice"
          }
        }
      },
      {
        __typename: "ProductCountableEdge",
        node: {
          __typename: "Product",
          id: "UHJvZHVjdDoxMTU=",
          isPublished: true,
          name: "Black Hoodie",
          productType: {
            __typename: "ProductType",
            id: "UHJvZHVjdFR5cGU6MTQ=",
            name: "Top (clothing)"
          }
        }
      }
    ],
    pageInfo: {
      __typename: "PageInfo",
      endCursor: "YXJyYXljb25uZWN0aW9uOjM=",
      hasNextPage: false,
      hasPreviousPage: false,
      startCursor: "YXJyYXljb25uZWN0aW9uOjA="
    }
  },
  startDate: "2019-01-03",
  type: "PERCENTAGE" as SaleType,
  value: 30
};
