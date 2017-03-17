import React, { Component, PropTypes } from 'react';
import InlineSVG from 'react-inlinesvg';

import arrowUpIcon from '../../../../../templates/svg/arrow-up-icon.svg';
import arrowDownIcon from '../../../../../templates/svg/arrow-down-icon.svg';

export default class sortBy extends Component {

  constructor(props) {
    super(props);
    this.state = {
      visibility: false
    };
  }

  static propTypes = {
    setSorting: PropTypes.func,
    sortedValue: PropTypes.string
  }

  setSorting = (event) => {
    const value = event.currentTarget.className;
    this.props.setSorting(value);
    this.changeVisibility();
  }

  changeVisibility = () => {
    this.setState({
      visibility: !this.state.visibility
    });
  }

  render() {
    const { sortedValue } = this.props;
    const { visibility } = this.state;
    return (
      <div className="sort-by">
        <div className={visibility ? ('click-area') : ('click-area hide')} onClick={this.changeVisibility}></div>
        <button className="btn btn-link" onClick={this.changeVisibility}>
          {sortedValue ? (
            sortedValue.search('-') ? (
              <div>
                <span>{gettext('Sort by:')} <strong>{sortedValue}</strong></span>
                <div className="sort-order-icon">
                  <InlineSVG key="arrowUpIcon" src={arrowUpIcon} />
                </div>
              </div>
            ) : (
               <div>
                <span>{gettext('Sort by:')} <strong>{sortedValue.replace('-', '')}</strong></span>
                <div className="sort-order-icon">
                  <InlineSVG key="arrowDownIcon" src={arrowDownIcon} />
                </div>
              </div>
            )
          ) : (
            <span>{gettext('Sort by:')} <strong>{gettext('default')}</strong></span>
          )}
        </button>
        {visibility && (
          <ul className="sort-list">
            <li className="name">
              <div className="row">
                <div className="col-6">{gettext('Sort by:')} <strong>{gettext('Name')}</strong></div>
                <div className="col-6">
                    <div className="name" onClick={this.setSorting}>
                      <span>{gettext('ascending')}</span>
                      <div className="float-right sort-order-icon">
                        <InlineSVG src={arrowUpIcon} />
                      </div>
                    </div>
                </div>
              </div>
              <div className="row">
                <div className="col-6"></div>
                <div className="col-6">
                    <div className="-name" onClick={this.setSorting}>
                      <span>{gettext('descending')}</span>
                      <div className="float-right sort-order-icon">
                        <InlineSVG src={arrowDownIcon} />
                      </div>
                    </div>
                </div>
              </div>
            </li>
            <li className="price">
              <div className="row">
                <div className="col-6">{gettext('Sort by:')} <strong>{gettext('Price')}</strong></div>
                <div className="col-6">
                    <div className="price" onClick={this.setSorting}>
                      <span>{gettext('ascending')}</span>
                      <div className="float-right sort-order-icon">
                        <InlineSVG src={arrowUpIcon} />
                      </div>
                    </div>
                </div>
              </div>
              <div className="row">
                <div className="col-6"></div>
                <div className="col-6">
                    <div className="-price" onClick={this.setSorting}>
                      <span>{gettext('descending')}</span>
                      <div className="float-right sort-order-icon">
                        <InlineSVG src={arrowDownIcon} />
                      </div>
                    </div>
                </div>
              </div>
            </li>
          </ul>
        )}
      </div>
    );
  }
}
