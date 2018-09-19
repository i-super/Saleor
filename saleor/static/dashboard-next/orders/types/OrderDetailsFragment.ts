/* tslint:disable */
// This file was automatically generated and should not be edited.

import { AddressCountry, OrderEventsEmails, OrderEvents, FulfillmentStatus, PaymentStatusEnum, OrderStatus } from "./../../types/globalTypes";

// ====================================================
// GraphQL fragment: OrderDetailsFragment
// ====================================================

export interface OrderDetailsFragment_billingAddress {
  __typename: "Address";
  id: string;
  city: string;
  cityArea: string;
  companyName: string;
  country: AddressCountry;
  countryArea: string;
  firstName: string;
  lastName: string;
  phone: string | null;
  postalCode: string;
  streetAddress1: string;
  streetAddress2: string;
}

export interface OrderDetailsFragment_events_user {
  __typename: "User";
  email: string;
}

export interface OrderDetailsFragment_events {
  __typename: "OrderEvent";
  id: string;
  amount: number | null;
  date: any | null;
  email: string | null;
  emailType: OrderEventsEmails | null;
  message: string | null;
  quantity: number | null;
  type: OrderEvents | null;
  user: OrderDetailsFragment_events_user | null;
}

export interface OrderDetailsFragment_fulfillments_lines_edges_node_orderLine {
  __typename: "OrderLine";
  id: string;
  productName: string;
}

export interface OrderDetailsFragment_fulfillments_lines_edges_node {
  __typename: "FulfillmentLine";
  id: string;
  orderLine: OrderDetailsFragment_fulfillments_lines_edges_node_orderLine;
  quantity: number;
}

export interface OrderDetailsFragment_fulfillments_lines_edges {
  __typename: "FulfillmentLineCountableEdge";
  node: OrderDetailsFragment_fulfillments_lines_edges_node;
}

export interface OrderDetailsFragment_fulfillments_lines {
  __typename: "FulfillmentLineCountableConnection";
  edges: OrderDetailsFragment_fulfillments_lines_edges[];
}

export interface OrderDetailsFragment_fulfillments {
  __typename: "Fulfillment";
  id: string;
  lines: OrderDetailsFragment_fulfillments_lines | null;
  status: FulfillmentStatus;
  trackingNumber: string;
}

export interface OrderDetailsFragment_lines_edges_node_unitPrice_gross {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_lines_edges_node_unitPrice_net {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_lines_edges_node_unitPrice {
  __typename: "TaxedMoney";
  gross: OrderDetailsFragment_lines_edges_node_unitPrice_gross;
  net: OrderDetailsFragment_lines_edges_node_unitPrice_net;
}

export interface OrderDetailsFragment_lines_edges_node {
  __typename: "OrderLine";
  id: string;
  productName: string;
  productSku: string;
  quantity: number;
  quantityFulfilled: number;
  unitPrice: OrderDetailsFragment_lines_edges_node_unitPrice | null;
}

export interface OrderDetailsFragment_lines_edges {
  __typename: "OrderLineCountableEdge";
  node: OrderDetailsFragment_lines_edges_node;
}

export interface OrderDetailsFragment_lines {
  __typename: "OrderLineCountableConnection";
  edges: OrderDetailsFragment_lines_edges[];
}

export interface OrderDetailsFragment_shippingAddress {
  __typename: "Address";
  id: string;
  city: string;
  cityArea: string;
  companyName: string;
  country: AddressCountry;
  countryArea: string;
  firstName: string;
  lastName: string;
  phone: string | null;
  postalCode: string;
  streetAddress1: string;
  streetAddress2: string;
}

export interface OrderDetailsFragment_shippingMethod {
  __typename: "ShippingMethod";
  id: string;
}

export interface OrderDetailsFragment_shippingPrice_gross {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_shippingPrice {
  __typename: "TaxedMoney";
  gross: OrderDetailsFragment_shippingPrice_gross;
}

export interface OrderDetailsFragment_subtotal_gross {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_subtotal {
  __typename: "TaxedMoney";
  gross: OrderDetailsFragment_subtotal_gross;
}

export interface OrderDetailsFragment_total_gross {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_total_tax {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_total {
  __typename: "TaxedMoney";
  gross: OrderDetailsFragment_total_gross;
  tax: OrderDetailsFragment_total_tax;
}

export interface OrderDetailsFragment_totalAuthorized {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_totalCaptured {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface OrderDetailsFragment_user {
  __typename: "User";
  id: string;
  email: string;
}

export interface OrderDetailsFragment_availableShippingMethods {
  __typename: "ShippingMethod";
  id: string;
  name: string;
}

export interface OrderDetailsFragment {
  __typename: "Order";
  id: string;
  billingAddress: OrderDetailsFragment_billingAddress | null;
  created: any;
  events: (OrderDetailsFragment_events | null)[] | null;
  fulfillments: (OrderDetailsFragment_fulfillments | null)[];
  lines: OrderDetailsFragment_lines | null;
  number: string | null;
  paymentStatus: PaymentStatusEnum | null;
  shippingAddress: OrderDetailsFragment_shippingAddress | null;
  shippingMethod: OrderDetailsFragment_shippingMethod | null;
  shippingMethodName: string | null;
  shippingPrice: OrderDetailsFragment_shippingPrice | null;
  status: OrderStatus;
  subtotal: OrderDetailsFragment_subtotal | null;
  total: OrderDetailsFragment_total | null;
  totalAuthorized: OrderDetailsFragment_totalAuthorized | null;
  totalCaptured: OrderDetailsFragment_totalCaptured | null;
  user: OrderDetailsFragment_user | null;
  availableShippingMethods: (OrderDetailsFragment_availableShippingMethods | null)[] | null;
}
