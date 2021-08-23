import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { NgbModule } from '@ng-bootstrap/ng-bootstrap';

import { DownloadConfirmComponent } from './download-confirm/download-confirm.component';
import { CartcontrolComponent } from './cartcontrol/cartcontrol.component';
import { BundleplanComponent } from './bundleplan/bundleplan.component';
import { CartService } from "./cart.service";
import { DatacartComponent } from './datacart.component';
import { SharedModule } from '../shared/shared.module';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TreeModule, FieldsetModule, DialogModule, OverlayPanelModule } from 'primeng/primeng';
import { TreeTableModule } from 'primeng/treetable';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';
import { TreetableComponent } from './treetable/treetable.component';
import { LeaveWhileDownloadingGuard } from './leave.guard';


@NgModule({
  declarations: [ 
      DatacartComponent, 
      DownloadConfirmComponent, 
      CartcontrolComponent, 
      BundleplanComponent, TreetableComponent
  ],
  imports: [
      CommonModule, SharedModule, ProgressSpinnerModule, NgbModule, TreeModule, FieldsetModule,
      DialogModule, OverlayPanelModule, TreeTableModule, ButtonModule, TooltipModule
  ],
  exports: [
    DatacartComponent
  ],
  entryComponents: [
    DownloadConfirmComponent
  ],
  providers: [
    CartService,
    LeaveWhileDownloadingGuard
  ]
})
export class DatacartModule {

 }
