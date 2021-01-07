import { Component, OnInit, Input } from '@angular/core';
import { DataCartStatus } from '../../datacart/cartstatus';

@Component({
  selector: 'app-downloadstatus',
  templateUrl: './downloadstatus.component.html',
  styleUrls: ['./downloadstatus.component.css']
})
export class DownloadstatusComponent implements OnInit {
    dataCartStatus: DataCartStatus;

    @Input() inBrowser: boolean;

    constructor() { }

    ngOnInit() {
        if(this.inBrowser){
            this.dataCartStatus = DataCartStatus.openCartStatus();
            window.addEventListener("storage", this.cartChanged.bind(this));
        }
    }

    /**
     * When storage changed, if it's dataCartStatus, loop through each cart and restore dataCartStatus object.
     * The display will automatically pick up the data.
     * @param ev Event - storage
     */
    cartChanged(ev){
        this.dataCartStatus.restore();

        if(ev.key == this.dataCartStatus.getName()){
            this.dataCartStatus.restore();
        }
    }

    /**
     * Get keys of dataCartStatus. The UI uses it to display download progress
     */
    get getKeys(){
        return Object.keys(this.dataCartStatus.dataCartStatusItems)
    }

    /**
     * Check if we want to display the title bar of the download status. 
     * If no status to display, we will not display the title bar.
     */
    get showDownloadStatus(){
        let hasStatusToDisplay: boolean = false;

        for(let key in this.dataCartStatus.dataCartStatusItems){
            if(this.dataCartStatus.dataCartStatusItems[key].statusData.downloadPercentage > 0){
                hasStatusToDisplay = true;
                break;
            }
        }

        return hasStatusToDisplay;
    }

    /**
     * Remove the status item from the object
     * @param key the status item to be removed
     */
    removeStatusItem(key: string){
        this.dataCartStatus.restore();
        delete this.dataCartStatus.dataCartStatusItems[key];
        this.dataCartStatus.save();
    }
}
