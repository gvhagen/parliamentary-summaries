// src/app/services/summary.service.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, combineLatest, map } from 'rxjs';
import { 
  ParliamentarySummary, 
  ParliamentaryDocument, 
  TopicFilter, 
  PartyFilter, 
  SearchFilter,
  EnhancedTopic,
  EnhancedPartyPosition
} from '../models/parliamentary-summary.model';

@Injectable({
  providedIn: 'root'
})
export class SummaryService {
  private documentsSubject = new BehaviorSubject<ParliamentaryDocument[]>([]);
  private topicFiltersSubject = new BehaviorSubject<TopicFilter[]>([]);
  private partyFiltersSubject = new BehaviorSubject<PartyFilter[]>([]);
  private searchFilterSubject = new BehaviorSubject<SearchFilter>({
    query: '',
    includeTopics: true,
    includePositions: true,
    includeDecisions: true,
    includeContext: true,
    includeReasoning: true
  });

  public documents$ = this.documentsSubject.asObservable();
  public topicFilters$ = this.topicFiltersSubject.asObservable();
  public partyFilters$ = this.partyFiltersSubject.asObservable();
  public searchFilter$ = this.searchFilterSubject.asObservable();

  // Enhanced filtered documents based on current filters
  public filteredDocuments$ = combineLatest([
    this.documents$,
    this.topicFilters$,
    this.partyFilters$,
    this.searchFilter$
  ]).pipe(
    map(([documents, topicFilters, partyFilters, searchFilter]) => 
      this.applyEnhancedFilters(documents, topicFilters, partyFilters, searchFilter)
    )
  );

  constructor(private http: HttpClient) {
    this.loadDocuments();
  }

  private async loadDocuments(): Promise<void> {
    try {
      // For now, we'll load from a single JSON file
      // Later you can expand this to load multiple files or use an API
      const summary = await this.http.get<ParliamentarySummary>('/assets/summaries/sample-summary.json').toPromise();
      
      if (summary) {
        const document: ParliamentaryDocument = {
          id: summary.meeting_info.verslag_id,
          title: summary.meeting_info.vergadering_titel,
          date: new Date(summary.meeting_info.vergadering_datum),
          summary: summary
        };

        this.documentsSubject.next([document]);
        this.initializeEnhancedFilters([document]);
      }
    } catch (error) {
      console.error('Error loading documents:', error);
      // For development, create a mock document if file doesn't exist
      this.createEnhancedMockDocument();
    }
  }

  private createEnhancedMockDocument(): void {
    const mockSummary: ParliamentarySummary = {
      executive_summary: "This parliamentary meeting covered climate policy, housing regulation, and agricultural reforms with detailed context and party positions including specific proposals and reasoning.",
      main_topics: [
        {
          topic: "Climate Policy",
          context: {
            why_discussed: "EU requirement for 55% emission reduction by 2030",
            background: "Netherlands currently at 25% reduction, needs urgent action",
            stakes: "Failure to meet targets results in EU fines and climate damage"
          },
          summary: "Discussion about emission reduction targets and energy transition including required infrastructure investments",
          party_positions: {
            "VVD": {
              position: "Advocates for practical implementation",
              specific_proposals: ["Market-based carbon pricing", "Gradual coal phase-out by 2028"],
              reasoning: "Avoid damaging economic competitiveness and job losses",
              key_evidence: "Cited German industry concerns about carbon leakage"
            },
            "GroenLinks-PvdA": {
              position: "Pushes for more ambitious action",
              specific_proposals: ["Immediate coal phase-out", "Mandatory solar panels on new buildings"],
              reasoning: "Climate emergency requires urgent action",
              key_evidence: "Referenced latest IPCC report on tipping points"
            },
            "PVV": {
              position: "Opposes additional measures",
              specific_proposals: ["Maintain current policies", "No new climate taxes"],
              reasoning: "Protect citizens from rising energy costs",
              key_evidence: "Pointed to high energy bills affecting households"
            }
          },
          outcome: "Agreement to address grid investment costs in Spring budget"
        },
        {
          topic: "Housing Regulation",
          context: {
            why_discussed: "Rising complaints about housing quality and rent increases",
            background: "Good Landlord Act enforcement showing mixed results",
            stakes: "Housing crisis affects 400,000 households seeking affordable housing"
          },
          summary: "Enforcement of Good Landlord Act and tenant protection measures",
          party_positions: {
            "GroenLinks-PvdA": {
              position: "Called for stronger enforcement",
              specific_proposals: ["Higher fines for bad landlords", "Tenant protection fund"],
              reasoning: "Current enforcement insufficient to protect tenants",
              key_evidence: "Municipal data showing 40% violation rate"
            },
            "VVD": {
              position: "Supported current framework with improvements",
              specific_proposals: ["Better coordination between municipalities", "Digital complaint system"],
              reasoning: "Avoid over-regulation that reduces housing supply",
              key_evidence: "Industry warning about investment decline"
            }
          },
          outcome: "Minister agreed to gather enforcement data and improve coordination"
        }
      ],
      key_decisions: [
        "Approval of motion to expedite power grid permits",
        "Agreement to schedule debate about grid costs within three weeks",
        "Commitment to gather municipal housing enforcement data by June"
      ],
      political_dynamics: "Significant divisions between parties on climate policy implementation speed, with progressive parties pushing for urgency while conservative parties emphasized economic impacts. Housing enforcement saw more consensus on need for improvement.",
      next_steps: [
        "Present cost mitigation measures for grid investments in Spring budget",
        "Develop farm-specific emission targets by end of year",
        "Municipal housing enforcement data collection by June 2025"
      ],
      meeting_info: {
        vergadering_titel: "61e vergadering, dinsdag 11 maart 2025",
        vergadering_datum: "2025-03-11T00:00:00+01:00",
        verslag_id: "mock-enhanced-123",
        status: "Gecorrigeerd"
      },
      processing_info: {
        chunks_processed: 16,
        total_topics_found: 2,
        processing_date: new Date().toISOString(),
        enhancement_level: 'detailed',
        ai_model: 'claude-3-haiku-20240307'
      }
    };

    const mockDocument: ParliamentaryDocument = {
      id: 'mock-enhanced-123',
      title: '61e vergadering, dinsdag 11 maart 2025',
      date: new Date('2025-03-11'),
      summary: mockSummary
    };

    this.documentsSubject.next([mockDocument]);
    this.initializeEnhancedFilters([mockDocument]);
  }

  private initializeEnhancedFilters(documents: ParliamentaryDocument[]): void {
    // Extract unique topics with counts
    const topicCounts = new Map<string, number>();
    const partyCounts = new Map<string, number>();

    documents.forEach(doc => {
      doc.summary.main_topics.forEach(topic => {
        topicCounts.set(topic.topic, (topicCounts.get(topic.topic) || 0) + 1);
        
        Object.keys(topic.party_positions).forEach(party => {
          partyCounts.set(party, (partyCounts.get(party) || 0) + 1);
        });
      });
    });

    // Create enhanced topic filters
    const topicFilters: TopicFilter[] = Array.from(topicCounts.entries()).map(([topic, count]) => ({
      name: topic,
      selected: true,
      count: count
    }));

    // Create enhanced party filters with colors and counts
    const partyColors: { [key: string]: string } = {
      'VVD': '#0066CC',
      'PvdA': '#CC0000',
      'GroenLinks-PvdA': '#00AA00',
      'PVV': '#FFD700',
      'CDA': '#00AA55',
      'D66': '#FFAA00',
      'NSC': '#800080',
      'PvdD': '#006600',
      'ChristenUnie': '#0099CC',
      'SGP': '#FF6600',
      'SP': '#CC0000',
      'Minister': '#666666'
    };

    const partyFilters: PartyFilter[] = Array.from(partyCounts.entries()).map(([party, count]) => ({
      name: party,
      selected: true,
      color: partyColors[party] || '#666666',
      positions: count
    }));

    this.topicFiltersSubject.next(topicFilters);
    this.partyFiltersSubject.next(partyFilters);
  }

  private applyEnhancedFilters(
    documents: ParliamentaryDocument[],
    topicFilters: TopicFilter[],
    partyFilters: PartyFilter[],
    searchFilter: SearchFilter
  ): ParliamentaryDocument[] {
    const selectedTopics = topicFilters.filter(f => f.selected).map(f => f.name);
    const selectedParties = partyFilters.filter(f => f.selected).map(f => f.name);

    return documents.filter(doc => {
      // Apply topic filter
      const hasSelectedTopic = doc.summary.main_topics.some(topic => 
        selectedTopics.includes(topic.topic)
      );

      // Apply party filter
      const hasSelectedParty = doc.summary.main_topics.some(topic =>
        Object.keys(topic.party_positions).some(party =>
          selectedParties.includes(party)
        )
      );

      // Apply enhanced search filter
      const matchesSearch = this.matchesEnhancedSearchQuery(doc, searchFilter);

      return hasSelectedTopic && hasSelectedParty && matchesSearch;
    });
  }

  private matchesEnhancedSearchQuery(doc: ParliamentaryDocument, searchFilter: SearchFilter): boolean {
    if (!searchFilter.query.trim()) {
      return true;
    }

    const query = searchFilter.query.toLowerCase();
    const searchableText: string[] = [];

    // Add executive summary
    searchableText.push(doc.summary.executive_summary.toLowerCase());

    // Add topics if enabled
    if (searchFilter.includeTopics) {
      doc.summary.main_topics.forEach(topic => {
        searchableText.push(topic.topic.toLowerCase());
        searchableText.push(topic.summary.toLowerCase());
      });
    }

    // Add context if enabled
    if (searchFilter.includeContext) {
      doc.summary.main_topics.forEach(topic => {
        if (topic.context) {
          Object.values(topic.context).forEach(contextValue => {
            if (contextValue) {
              searchableText.push(contextValue.toLowerCase());
            }
          });
        }
      });
    }

    // Add party positions if enabled
    if (searchFilter.includePositions) {
      doc.summary.main_topics.forEach(topic => {
        Object.values(topic.party_positions).forEach(position => {
          if (typeof position === 'string') {
            searchableText.push(position.toLowerCase());
          } else {
            searchableText.push(position.position.toLowerCase());
            
            // Add specific proposals
            if (position.specific_proposals) {
              position.specific_proposals.forEach(proposal => {
                searchableText.push(proposal.toLowerCase());
              });
            }
          }
        });
      });
    }

    // Add reasoning if enabled
    if (searchFilter.includeReasoning) {
      doc.summary.main_topics.forEach(topic => {
        Object.values(topic.party_positions).forEach(position => {
          if (typeof position === 'object' && position.reasoning) {
            searchableText.push(position.reasoning.toLowerCase());
          }
          if (typeof position === 'object' && position.key_evidence) {
            searchableText.push(position.key_evidence.toLowerCase());
          }
        });
      });
    }

    // Add decisions if enabled
    if (searchFilter.includeDecisions) {
      doc.summary.key_decisions.forEach(decision => {
        searchableText.push(decision.toLowerCase());
      });
    }

    // Add next steps
    if (doc.summary.next_steps) {
      doc.summary.next_steps.forEach(step => {
        searchableText.push(step.toLowerCase());
      });
    }

    return searchableText.some(text => text.includes(query));
  }

  // Public methods for updating filters
  updateTopicFilter(topicName: string, selected: boolean): void {
    const currentFilters = this.topicFiltersSubject.value;
    const updatedFilters = currentFilters.map(filter =>
      filter.name === topicName ? { ...filter, selected } : filter
    );
    this.topicFiltersSubject.next(updatedFilters);
  }

  updatePartyFilter(partyName: string, selected: boolean): void {
    const currentFilters = this.partyFiltersSubject.value;
    const updatedFilters = currentFilters.map(filter =>
      filter.name === partyName ? { ...filter, selected } : filter
    );
    this.partyFiltersSubject.next(updatedFilters);
  }

  updateSearchFilter(searchFilter: Partial<SearchFilter>): void {
    const currentFilter = this.searchFilterSubject.value;
    this.searchFilterSubject.next({ ...currentFilter, ...searchFilter });
  }

  // Method to load additional enhanced summary files
  async loadEnhancedSummaryFile(filename: string): Promise<void> {
    try {
      const summary = await this.http.get<ParliamentarySummary>(`/assets/summaries/${filename}`).toPromise();
      
      if (summary) {
        const document: ParliamentaryDocument = {
          id: summary.meeting_info.verslag_id,
          title: summary.meeting_info.vergadering_titel,
          date: new Date(summary.meeting_info.vergadering_datum),
          summary: summary
        };

        const currentDocuments = this.documentsSubject.value;
        const updatedDocuments = [...currentDocuments, document];
        
        this.documentsSubject.next(updatedDocuments);
        this.initializeEnhancedFilters(updatedDocuments);
      }
    } catch (error) {
      console.error(`Error loading enhanced summary file ${filename}:`, error);
    }
  }

  // Method to load multiple summary files
  async loadMultipleSummaryFiles(filenames: string[]): Promise<void> {
    const documents: ParliamentaryDocument[] = [];
    
    for (const filename of filenames) {
      try {
        const summary = await this.http.get<ParliamentarySummary>(`/assets/summaries/${filename}`).toPromise();
        
        if (summary) {
          const document: ParliamentaryDocument = {
            id: summary.meeting_info.verslag_id,
            title: summary.meeting_info.vergadering_titel,
            date: new Date(summary.meeting_info.vergadering_datum),
            summary: summary
          };
          documents.push(document);
        }
      } catch (error) {
        console.warn(`Could not load ${filename}:`, error);
      }
    }
    
    if (documents.length > 0) {
      const currentDocuments = this.documentsSubject.value;
      const updatedDocuments = [...currentDocuments, ...documents];
      
      this.documentsSubject.next(updatedDocuments);
      this.initializeEnhancedFilters(updatedDocuments);
    }
  }

  getDocumentById(id: string): Observable<ParliamentaryDocument | undefined> {
    return this.documents$.pipe(
      map(documents => documents.find(doc => doc.id === id))
    );
  }

  // Enhanced utility methods
  getTopicsByParty(partyName: string): Observable<EnhancedTopic[]> {
    return this.documents$.pipe(
      map(documents => {
        const topics: EnhancedTopic[] = [];
        documents.forEach(doc => {
          doc.summary.main_topics.forEach(topic => {
            if (topic.party_positions[partyName]) {
              topics.push(topic);
            }
          });
        });
        return topics;
      })
    );
  }

  getPartiesByTopic(topicName: string): Observable<string[]> {
    return this.documents$.pipe(
      map(documents => {
        const parties = new Set<string>();
        documents.forEach(doc => {
          doc.summary.main_topics.forEach(topic => {
            if (topic.topic === topicName) {
              Object.keys(topic.party_positions).forEach(party => {
                parties.add(party);
              });
            }
          });
        });
        return Array.from(parties);
      })
    );
  }

  
}