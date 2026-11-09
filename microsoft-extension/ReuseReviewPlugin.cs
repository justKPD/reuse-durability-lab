using System;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;
using Microsoft.Xrm.Sdk.Messages;

[assembly: System.Reflection.AssemblyVersion("1.0.1.3")]
[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.6.2")]

namespace Drona.ReuseReview {
 public static class Shared {
  public static string S(Entity e,string k){return e.GetAttributeValue<string>(k)??"";}
  public static string Hash(string text){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-","").ToLowerInvariant();}
  public static bool Parent(IPluginExecutionContext c,string message,string entity=null){
   for(var p=c.ParentContext;p!=null;p=p.ParentContext)
    if(p.MessageName==message&&(entity==null||p.PrimaryEntityName==entity))return true;
   return false;
  }
  public static IOrganizationService Service(IServiceProvider p,IPluginExecutionContext c){
   return ((IOrganizationServiceFactory)p.GetService(typeof(IOrganizationServiceFactory))).CreateOrganizationService(c.UserId);
  }
 }
 public class CaseGuard:IPlugin {
  public void Execute(IServiceProvider provider){
   var c=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
   if(!c.InputParameters.Contains("Target")||!(c.InputParameters["Target"] is Entity))return;
   var t=(Entity)c.InputParameters["Target"];
   if(t.LogicalName!="drn_reviewcase")return;
   if(Shared.Parent(c,"drn_CommitReview"))return;
   if(Shared.Parent(c,"Create","drn_reviewrequest"))return;
   if(c.MessageName=="Create"){
    if(string.IsNullOrWhiteSpace(Shared.S(t,"drn_casekey")))throw new InvalidPluginExecutionException("CASE_KEY_REQUIRED");
    if(string.IsNullOrWhiteSpace(Shared.S(t,"drn_payload")))throw new InvalidPluginExecutionException("CONTENT_REQUIRED");
    t["drn_revision"]=1;t["drn_contenthash"]=Shared.Hash(Shared.S(t,"drn_payload"));t["drn_status"]="Pending";
    t["drn_lastrequestkey"]=null;
    if(string.IsNullOrEmpty(Shared.S(t,"drn_reviewerid")))t["drn_reviewerid"]=c.InitiatingUserId.ToString("D");
    return;
   }
   if(t.Contains("drn_status")||t.Contains("drn_lastrequestkey")||t.Contains("drn_contenthash")||t.Contains("drn_revision"))
    throw new InvalidPluginExecutionException("DECISION_FIELDS_SERVER_CONTROLLED");
   if(t.Contains("drn_payload")||t.Contains("drn_scopehash")||t.Contains("drn_reviewerid")){
    var service=Shared.Service(provider,c);
    var old=service.Retrieve(t.LogicalName,t.Id,new ColumnSet("drn_payload","drn_revision","drn_scopehash"));
    string payload=t.Contains("drn_payload")?Shared.S(t,"drn_payload"):Shared.S(old,"drn_payload");
    if(string.IsNullOrWhiteSpace(payload))throw new InvalidPluginExecutionException("CONTENT_REQUIRED");
    string scope=t.Contains("drn_scopehash")?Shared.S(t,"drn_scopehash"):Shared.S(old,"drn_scopehash");
    // Scope identity participates in approval identity even when the action payload is unchanged.
    t["drn_revision"]=old.GetAttributeValue<int>("drn_revision")+1;
    t["drn_contenthash"]=Shared.Hash(payload);
    t["drn_status"]="Pending";t["drn_lastrequestkey"]=null;
   }
  }
 }
 public class RequestGuard:IPlugin {
  public void Execute(IServiceProvider provider){
   var c=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
   if(!c.InputParameters.Contains("Target")||!(c.InputParameters["Target"] is Entity))return;
   var t=(Entity)c.InputParameters["Target"]; if(t.LogicalName!="drn_reviewrequest")return;
   var service=Shared.Service(provider,c);
   if(c.MessageName=="Create"){
    Guid id;
    if(!Guid.TryParse(Shared.S(t,"drn_caseid"),out id))throw new InvalidPluginExecutionException("CASE_REQUIRED");
    string key=Shared.S(t,"drn_requestkey");
    if(string.IsNullOrWhiteSpace(key)||key.Length>120)throw new InvalidPluginExecutionException("REQUEST_KEY_REQUIRED");
    var row=service.Retrieve("drn_reviewcase",id,new ColumnSet(true));
    string reviewer=Shared.S(row,"drn_reviewerid");
    t["drn_revision"]=row.GetAttributeValue<int>("drn_revision");t["drn_contenthash"]=Shared.S(row,"drn_contenthash");
    t["drn_reviewerid"]=reviewer;t["drn_status"]="Pending";t["drn_outcome"]="";
    var update=new Entity("drn_reviewcase",id);update.RowVersion=row.RowVersion;update["drn_lastrequestkey"]=key;update["drn_status"]="Pending";
    service.Execute(new UpdateRequest{Target=update,ConcurrencyBehavior=ConcurrencyBehavior.IfRowVersionMatches});
    return;
   }
   if(Shared.Parent(c,"drn_CommitReview"))return;
   if(t.Attributes.Keys.Any(k=>k!="drn_name"&&k!="drn_flowrunid"&&k!="drn_reviewrequestid"))
    throw new InvalidPluginExecutionException("REQUEST_IDENTITY_IMMUTABLE");
  }
 }
 public class DecisionGuard:IPlugin {
  public void Execute(IServiceProvider provider){
   var c=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
   if(!Shared.Parent(c,"drn_CommitReview"))throw new InvalidPluginExecutionException("DECISION_REQUIRES_COMMIT_API");
  }
 }
 public class CommitReview:IPlugin {
  public void Execute(IServiceProvider provider){
   var c=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
   var service=Shared.Service(provider,c);
   if(!c.IsInTransaction)throw new InvalidPluginExecutionException("TRANSACTION_REQUIRED");
   string key=(string)c.InputParameters["RequestKey"];
   string outcome=(string)c.InputParameters["Outcome"];
   if(outcome!="Approve"&&outcome!="Reject")throw new InvalidPluginExecutionException("INVALID_OUTCOME");
   var q=new QueryExpression("drn_reviewrequest"){ColumnSet=new ColumnSet(true),TopCount=2};
   q.Criteria.AddCondition("drn_requestkey",ConditionOperator.Equal,key);
   var requests=service.RetrieveMultiple(q).Entities;
   if(requests.Count!=1)throw new InvalidPluginExecutionException("UNIQUE_REQUEST_REQUIRED");
   var req=requests[0];
   if(Shared.S(req,"drn_reviewerid")!=c.InitiatingUserId.ToString("D"))throw new InvalidPluginExecutionException("ASSIGNED_REVIEWER_REQUIRED");
   var row=service.Retrieve("drn_reviewcase",Guid.Parse(Shared.S(req,"drn_caseid")),new ColumnSet(true));
   bool current=row.GetAttributeValue<int>("drn_revision")==req.GetAttributeValue<int>("drn_revision")&&Shared.S(row,"drn_contenthash")==Shared.S(req,"drn_contenthash")&&Shared.S(row,"drn_lastrequestkey")==key;
   var dq=new QueryExpression("drn_reviewdecision"){ColumnSet=new ColumnSet(true),TopCount=2};
   dq.Criteria.AddCondition("drn_requestkey",ConditionOperator.Equal,key);
   var decisions=service.RetrieveMultiple(dq).Entities;
   if(decisions.Count>0){
    var d=decisions[0];
    if(Shared.S(d,"drn_outcome")!=outcome)throw new InvalidPluginExecutionException("DUPLICATE_OUTCOME_CONFLICT");
    c.OutputParameters["DecisionId"]=d.Id.ToString("D");c.OutputParameters["Status"]="AlreadyRecorded";c.OutputParameters["IsCurrent"]=current;return;
   }
   if(!current){
    var stale=new Entity("drn_reviewrequest",req.Id);stale["drn_status"]="Stale";service.Update(stale);
    c.OutputParameters["DecisionId"]="";c.OutputParameters["Status"]="Stale";c.OutputParameters["IsCurrent"]=false;return;
   }
   if(Shared.S(req,"drn_status")!="Pending")throw new InvalidPluginExecutionException("REQUEST_NOT_PENDING");
   // A declared failure-injection input proves rollback on synthetic records only.
   bool fail=c.InputParameters.Contains("SimulateWriteFailure")&&(bool)c.InputParameters["SimulateWriteFailure"];
   var update=new Entity("drn_reviewcase",row.Id);update.RowVersion=row.RowVersion;
   update["drn_status"]=outcome=="Approve"?"Approved":"Rejected";
   service.Execute(new UpdateRequest{Target=update,ConcurrencyBehavior=ConcurrencyBehavior.IfRowVersionMatches});
   if(fail)throw new InvalidPluginExecutionException("CONTROLLED_WRITE_FAILURE_ROLLBACK");
   var decision=new Entity("drn_reviewdecision");
   decision["drn_name"]=key;decision["drn_requestkey"]=key;decision["drn_caseid"]=row.Id.ToString("D");
   decision["drn_revision"]=req.GetAttributeValue<int>("drn_revision");decision["drn_contenthash"]=Shared.S(req,"drn_contenthash");
   decision["drn_actorid"]=c.InitiatingUserId.ToString("D");decision["drn_outcome"]=outcome;
   var decisionId=service.Create(decision);
   var requestUpdate=new Entity("drn_reviewrequest",req.Id);requestUpdate["drn_status"]=outcome=="Approve"?"Approved":"Rejected";
   requestUpdate["drn_outcome"]=outcome;service.Update(requestUpdate);
   c.OutputParameters["DecisionId"]=decisionId.ToString("D");c.OutputParameters["Status"]=outcome=="Approve"?"Approved":"Rejected";c.OutputParameters["IsCurrent"]=true;
  }
 }
}


namespace Drona.ReuseReview {
 public class RevisionSnapshot:IPlugin {
  public void Execute(IServiceProvider provider){
   var c=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
   if(c.PrimaryEntityName!="drn_reviewcase")return;
   var service=Shared.Service(provider,c);
   var row=service.Retrieve("drn_reviewcase",c.PrimaryEntityId,new ColumnSet(true));
   var q=new QueryExpression("drn_caserevision"){ColumnSet=new ColumnSet("drn_contenthash","drn_scopehash"),TopCount=1};
   q.Criteria.AddCondition("drn_caseid",ConditionOperator.Equal,row.Id.ToString("D"));
   q.Criteria.AddCondition("drn_revision",ConditionOperator.Equal,row.GetAttributeValue<int>("drn_revision"));
   var found=service.RetrieveMultiple(q).Entities;
   if(found.Count>0){
    if(Shared.S(found[0],"drn_contenthash")!=Shared.S(row,"drn_contenthash")||Shared.S(found[0],"drn_scopehash")!=Shared.S(row,"drn_scopehash"))
     throw new InvalidPluginExecutionException("REVISION_SNAPSHOT_CONFLICT");
    return;
   }
   var v=new Entity("drn_caserevision");
   v["drn_name"]="Revision "+row.GetAttributeValue<int>("drn_revision");
   v["drn_caseid"]=row.Id.ToString("D");v["drn_revision"]=row.GetAttributeValue<int>("drn_revision");
   v["drn_contenthash"]=Shared.S(row,"drn_contenthash");v["drn_scopehash"]=Shared.S(row,"drn_scopehash");v["drn_payload"]=Shared.S(row,"drn_payload");
   c.SharedVariables["drn_SnapshotAuthority"]=row.Id.ToString("D")+"|"+row.GetAttributeValue<int>("drn_revision")+"|"+Shared.S(row,"drn_contenthash");
   service.Create(v);
  }
 }
 public class RevisionGuard:IPlugin {
  public void Execute(IServiceProvider provider){
   var c=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
   if(c.MessageName!="Create"||!c.InputParameters.Contains("Target")||!(c.InputParameters["Target"] is Entity))
    throw new InvalidPluginExecutionException("REVISION_SNAPSHOT_IMMUTABLE");
   var target=(Entity)c.InputParameters["Target"];
   string expected=Shared.S(target,"drn_caseid")+"|"+target.GetAttributeValue<int>("drn_revision")+"|"+Shared.S(target,"drn_contenthash");
   bool authorized=false;
   for(var ctx=c;ctx!=null;ctx=ctx.ParentContext)
    if(ctx.SharedVariables.Contains("drn_SnapshotAuthority")&&ctx.SharedVariables["drn_SnapshotAuthority"] is string&&(string)ctx.SharedVariables["drn_SnapshotAuthority"]==expected)authorized=true;
   // Web API PATCH enters an Upsert pipeline whose primary-entity name may be empty.
   // Only trust an actual ancestor Target with the matching case identity.
   for(var ctx=c.ParentContext;ctx!=null;ctx=ctx.ParentContext){
    if((ctx.MessageName=="Create"||ctx.MessageName=="Update"||ctx.MessageName=="Upsert")&&ctx.InputParameters.Contains("Target")){
     var ancestor=ctx.InputParameters["Target"] as Entity;
     if(ancestor!=null&&ancestor.LogicalName=="drn_reviewcase"&&ancestor.Id.ToString("D")==Shared.S(target,"drn_caseid"))authorized=true;
    }
   }
   if(!authorized)throw new InvalidPluginExecutionException("REVISION_SNAPSHOT_IMMUTABLE");
   var service=Shared.Service(provider,c);
   var row=service.Retrieve("drn_reviewcase",Guid.Parse(Shared.S(target,"drn_caseid")),new ColumnSet(true));
   if(row.GetAttributeValue<int>("drn_revision")!=target.GetAttributeValue<int>("drn_revision")||
      Shared.S(row,"drn_contenthash")!=Shared.S(target,"drn_contenthash")||
      Shared.S(row,"drn_scopehash")!=Shared.S(target,"drn_scopehash")||
      Shared.S(row,"drn_payload")!=Shared.S(target,"drn_payload"))
    throw new InvalidPluginExecutionException("REVISION_SNAPSHOT_CONTENT_MISMATCH");
  }
 }
}
